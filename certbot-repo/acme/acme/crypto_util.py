"""Crypto utilities."""
import binascii
import contextlib
import logging
import os
import re
import socket
from typing import Callable
from typing import Tuple
from typing import Union

import josepy as jose
from OpenSSL import crypto
from OpenSSL import SSL

from acme import errors

logger = logging.getLogger(__name__)

# Default SSL method selected here is the most compatible, while secure
# SSL method: TLSv1_METHOD is only compatible with
# TLSv1_METHOD, while SSLv23_METHOD is compatible with all other
# methods, including TLSv2_METHOD (read more at
# https://www.openssl.org/docs/ssl/SSLv23_method.html). _serve_sni
# should be changed to use "set_options" to disable SSLv2 and SSLv3,
# in case it's used for things other than probing/serving!
_DEFAULT_SSL_METHOD = SSL.SSLv23_METHOD


class _DefaultCertSelection:
    def __init__(self, certs):
        self.certs = certs

    def __call__(self, connection):
        server_name = connection.get_servername()
        return self.certs.get(server_name, None)


class SSLSocket:  # pylint: disable=too-few-public-methods
    """SSL wrapper for sockets.

    :ivar socket sock: Original wrapped socket.
    :ivar dict certs: Mapping from domain names (`bytes`) to
        `OpenSSL.crypto.X509`.
    :ivar method: See `OpenSSL.SSL.Context` for allowed values.
    :ivar alpn_selection: Hook to select negotiated ALPN protocol for
        connection.
    :ivar cert_selection: Hook to select certificate for connection. If given,
        `certs` parameter would be ignored, and therefore must be empty.

    """
    def __init__(self, sock, certs=None,
            method=_DEFAULT_SSL_METHOD, alpn_selection=None,
            cert_selection=None):
        self.sock = sock
        self.alpn_selection = alpn_selection
        self.method = method
        if not cert_selection and not certs:
            raise ValueError("Neither cert_selection or certs specified.")
        if cert_selection and certs:
            raise ValueError("Both cert_selection and certs specified.")
        if cert_selection is None:
            cert_selection = _DefaultCertSelection(certs)
        self.cert_selection = cert_selection

    def __getattr__(self, name):
        return getattr(self.sock, name)

    def _pick_certificate_cb(self, connection):
        """SNI certificate callback.

        This method will set a new OpenSSL context object for this
        connection when an incoming connection provides an SNI name
        (in order to serve the appropriate certificate, if any).

        :param connection: The TLS connection object on which the SNI
            extension was received.
        :type connection: :class:`OpenSSL.Connection`

        """
        pair = self.cert_selection(connection)
        if pair is None:
            logger.debug("Certificate selection for server name %s failed, dropping SSL",
                         connection.get_servername())
            return
        key, cert = pair
        new_context = SSL.Context(self.method)
        new_context.set_options(SSL.OP_NO_SSLv2)
        new_context.set_options(SSL.OP_NO_SSLv3)
        new_context.use_privatekey(key)
        new_context.use_certificate(cert)
        if self.alpn_selection is not None:
            new_context.set_alpn_select_callback(self.alpn_selection)
        connection.set_context(new_context)

    class FakeConnection:
        """Fake OpenSSL.SSL.Connection."""

        # pylint: disable=missing-function-docstring

        def __init__(self, connection):
            self._wrapped = connection

        def __getattr__(self, name):
            return getattr(self._wrapped, name)

        def shutdown(self, *unused_args):
            # OpenSSL.SSL.Connection.shutdown doesn't accept any args
            return self._wrapped.shutdown()

    def accept(self):  # pylint: disable=missing-function-docstring
        sock, addr = self.sock.accept()

        context = SSL.Context(self.method)
        context.set_options(SSL.OP_NO_SSLv2)
        context.set_options(SSL.OP_NO_SSLv3)
        context.set_tlsext_servername_callback(self._pick_certificate_cb)
        if self.alpn_selection is not None:
            context.set_alpn_select_callback(self.alpn_selection)

        ssl_sock = self.FakeConnection(SSL.Connection(context, sock))
        ssl_sock.set_accept_state()

        logger.debug("Performing handshake with %s", addr)
        try:
            ssl_sock.do_handshake()
        except SSL.Error as error:
            # _pick_certificate_cb might have returned without
            # creating SSL context (wrong server name)
            raise socket.error(error)

        return ssl_sock, addr


def probe_sni(name, host, port=443, timeout=300, # pylint: disable=too-many-arguments
              method=_DEFAULT_SSL_METHOD, source_address=('', 0),
              alpn_protocols=None):
    """Probe SNI server for SSL certificate.

    :param bytes name: Byte string to send as the server name in the
        client hello message.
    :param bytes host: Host to connect to.
    :param int port: Port to connect to.
    :param int timeout: Timeout in seconds.
    :param method: See `OpenSSL.SSL.Context` for allowed values.
    :param tuple source_address: Enables multi-path probing (selection
        of source interface). See `socket.creation_connection` for more
        info. Available only in Python 2.7+.
    :param alpn_protocols: Protocols to request using ALPN.
    :type alpn_protocols: `list` of `bytes`

    :raises acme.errors.Error: In case of any problems.

    :returns: SSL certificate presented by the server.
    :rtype: OpenSSL.crypto.X509

    """
    context = SSL.Context(method)
    context.set_timeout(timeout)

    socket_kwargs = {'source_address': source_address}

    try:
        logger.debug(
            "Attempting to connect to %s:%d%s.", host, port,
            " from {0}:{1}".format(
                source_address[0],
                source_address[1]
            ) if any(source_address) else ""
        )
        socket_tuple: Tuple[str, int] = (host, port)
        sock = socket.create_connection(socket_tuple, **socket_kwargs)
    except socket.error as error:
        raise errors.Error(error)

    with contextlib.closing(sock) as client:
        client_ssl = SSL.Connection(context, client)
        client_ssl.set_connect_state()
        client_ssl.set_tlsext_host_name(name)  # pyOpenSSL>=0.13
        if alpn_protocols is not None:
            client_ssl.set_alpn_protos(alpn_protocols)
        try:
            client_ssl.do_handshake()
            client_ssl.shutdown()
        except SSL.Error as error:
            raise errors.Error(error)
    return client_ssl.get_peer_certificate()


def make_csr(private_key_pem, domains=None, must_staple=False, ipaddrs=None):
    """Generate a CSR containing domains or IPs as subjectAltNames.

    :param buffer private_key_pem: Private key, in PEM PKCS#8 format.
    :param list domains: List of DNS names to include in subjectAltNames of CSR.
    :param bool must_staple: Whether to include the TLS Feature extension (aka
        OCSP Must Staple: https://tools.ietf.org/html/rfc7633).
    :param list ipaddrs: List of IPaddress(type ipaddress.IPv4Address or ipaddress.IPv6Address)
    names to include in subbjectAltNames of CSR.
    params ordered this way for backward competablity when called by positional argument.
    :returns: buffer PEM-encoded Certificate Signing Request.
    """
    private_key = crypto.load_privatekey(
        crypto.FILETYPE_PEM, private_key_pem)
    csr = crypto.X509Req()
    sanlist = []
    # if domain or ip list not supplied make it empty list so it's easier to iterate
    if domains is None:
        domains = []
    if ipaddrs is None:
        ipaddrs = []
    if len(domains)+len(ipaddrs) == 0:
        raise ValueError("At least one of domains or ipaddrs parameter need to be not empty")
    for address in domains:
        sanlist.append('DNS:' + address)
    for ips in ipaddrs:
        sanlist.append('IP:' + ips.exploded)
    # make sure its ascii encoded
    san_string = ', '.join(sanlist).encode('ascii')
    # for IP san it's actually need to be octet-string,
    # but somewhere downsteam thankfully handle it for us
    extensions = [
        crypto.X509Extension(
            b'subjectAltName',
            critical=False,
            value=san_string
        ),
    ]
    if must_staple:
        extensions.append(crypto.X509Extension(
            b"1.3.6.1.5.5.7.1.24",
            critical=False,
            value=b"DER:30:03:02:01:05"))
    csr.add_extensions(extensions)
    csr.set_pubkey(private_key)
    csr.set_version(2)
    csr.sign(private_key, 'sha256')
    return crypto.dump_certificate_request(
        crypto.FILETYPE_PEM, csr)


def _pyopenssl_cert_or_req_all_names(loaded_cert_or_req):
    # unlike its name this only outputs DNS names, other type of idents will ignored
    common_name = loaded_cert_or_req.get_subject().CN
    sans = _pyopenssl_cert_or_req_san(loaded_cert_or_req)

    if common_name is None:
        return sans
    return [common_name] + [d for d in sans if d != common_name]


def _pyopenssl_cert_or_req_san(cert_or_req):
    """Get Subject Alternative Names from certificate or CSR using pyOpenSSL.

    .. todo:: Implement directly in PyOpenSSL!

    .. note:: Although this is `acme` internal API, it is used by
        `letsencrypt`.

    :param cert_or_req: Certificate or CSR.
    :type cert_or_req: `OpenSSL.crypto.X509` or `OpenSSL.crypto.X509Req`.

    :returns: A list of Subject Alternative Names that is DNS.
    :rtype: `list` of `unicode`

    """
    # This function finds SANs with dns name

    # constants based on PyOpenSSL certificate/CSR text dump
    part_separator = ":"
    prefix = "DNS" + part_separator

    sans_parts = _pyopenssl_extract_san_list_raw(cert_or_req)

    return [part.split(part_separator)[1]
            for part in sans_parts if part.startswith(prefix)]


def _pyopenssl_cert_or_req_san_ip(cert_or_req):
    """Get Subject Alternative Names IPs from certificate or CSR using pyOpenSSL.

    :param cert_or_req: Certificate or CSR.
    :type cert_or_req: `OpenSSL.crypto.X509` or `OpenSSL.crypto.X509Req`.

    :returns: A list of Subject Alternative Names that are IP Addresses.
    :rtype: `list` of `unicode`. note that this returns as string, not IPaddress object

    """

    # constants based on PyOpenSSL certificate/CSR text dump
    part_separator = ":"
    prefix = "IP Address" + part_separator

    sans_parts = _pyopenssl_extract_san_list_raw(cert_or_req)

    return [part[len(prefix):] for part in sans_parts if part.startswith(prefix)]


def _pyopenssl_extract_san_list_raw(cert_or_req):
    """Get raw SAN string from cert or csr, parse it as UTF-8 and return.

    :param cert_or_req: Certificate or CSR.
    :type cert_or_req: `OpenSSL.crypto.X509` or `OpenSSL.crypto.X509Req`.

    :returns: raw san strings, parsed byte as utf-8
    :rtype: `list` of `unicode`

    """
    # This function finds SANs by dumping the certificate/CSR to text and
    # searching for "X509v3 Subject Alternative Name" in the text. This method
    # is used to because in PyOpenSSL version <0.17 `_subjectAltNameString` methods are
    # not able to Parse IP Addresses in subjectAltName string.

    if isinstance(cert_or_req, crypto.X509):
        # pylint: disable=line-too-long
        func: Union[Callable[[int, crypto.X509Req], bytes], Callable[[int, crypto.X509], bytes]] = crypto.dump_certificate
    else:
        func = crypto.dump_certificate_request
    text = func(crypto.FILETYPE_TEXT, cert_or_req).decode("utf-8")
    # WARNING: this function does not support multiple SANs extensions.
    # Multiple X509v3 extensions of the same type is disallowed by RFC 5280.
    raw_san = re.search(r"X509v3 Subject Alternative Name:(?: critical)?\s*(.*)", text)

    parts_separator = ", "
    # WARNING: this function assumes that no SAN can include
    # parts_separator, hence the split!
    sans_parts = [] if raw_san is None else raw_san.group(1).split(parts_separator)
    return sans_parts


def gen_ss_cert(key, domains=None, not_before=None,
                validity=(7 * 24 * 60 * 60), force_san=True, extensions=None, ips=None):
    """Generate new self-signed certificate.

    :type domains: `list` of `unicode`
    :param OpenSSL.crypto.PKey key:
    :param bool force_san:
    :param extensions: List of additional extensions to include in the cert.
    :type extensions: `list` of `OpenSSL.crypto.X509Extension`
    :type ips: `list` of (`ipaddress.IPv4Address` or `ipaddress.IPv6Address`)

    If more than one domain is provided, all of the domains are put into
    ``subjectAltName`` X.509 extension and first domain is set as the
    subject CN. If only one domain is provided no ``subjectAltName``
    extension is used, unless `force_san` is ``True``.

    """
    assert domains or ips, "Must provide one or more hostnames or IPs for the cert."

    cert = crypto.X509()
    cert.set_serial_number(int(binascii.hexlify(os.urandom(16)), 16))
    cert.set_version(2)

    if extensions is None:
        extensions = []
    if domains is None:
        domains = []
    if ips is None:
        ips = []
    extensions.append(
        crypto.X509Extension(
            b"basicConstraints", True, b"CA:TRUE, pathlen:0"),
    )

    if len(domains) > 0:
        cert.get_subject().CN = domains[0]
    # TODO: what to put into cert.get_subject()?
    cert.set_issuer(cert.get_subject())

    sanlist = []
    for address in domains:
        sanlist.append('DNS:' + address)
    for ip in ips:
        sanlist.append('IP:' + ip.exploded)
    san_string = ', '.join(sanlist).encode('ascii')
    if force_san or len(domains) > 1 or len(ips) > 0:
        extensions.append(crypto.X509Extension(
            b"subjectAltName",
            critical=False,
            value=san_string
        ))

    cert.add_extensions(extensions)

    cert.gmtime_adj_notBefore(0 if not_before is None else not_before)
    cert.gmtime_adj_notAfter(validity)

    cert.set_pubkey(key)
    cert.sign(key, "sha256")
    return cert


def dump_pyopenssl_chain(chain, filetype=crypto.FILETYPE_PEM):
    """Dump certificate chain into a bundle.

    :param list chain: List of `OpenSSL.crypto.X509` (or wrapped in
        :class:`josepy.util.ComparableX509`).

    :returns: certificate chain bundle
    :rtype: bytes

    """
    # XXX: returns empty string when no chain is available, which
    # shuts up RenewableCert, but might not be the best solution...

    def _dump_cert(cert):
        if isinstance(cert, jose.ComparableX509):
            cert = cert.wrapped
        return crypto.dump_certificate(filetype, cert)

    # assumes that OpenSSL.crypto.dump_certificate includes ending
    # newline character
    return b"".join(_dump_cert(cert) for cert in chain)
