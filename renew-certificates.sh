#!/bin/bash
set -eo pipefail


echo ""
echo "ls /etc/letsencrypt/live/"
ls /etc/letsencrypt/live/

echo ""
echo "rm -rf /etc/letsencrypt/live/${CUSTOM_DOMAIN}*"
rm -rf /etc/letsencrypt/live/${CUSTOM_DOMAIN}*

echo ""
echo "ls /etc/letsencrypt/live/"
ls /etc/letsencrypt/live/

# echo "Setup letsencrypt context..."

# gsutil -m rsync -r "${LETSENCRYPT_BUCKET}" /etc/letsencrypt

# echo "Renewing certificate..."

# dns_provider_options="--dns-${DNS_PROVIDER}"
# if [ "${DNS_PROVIDER}" != "route53" ] && [ "${DNS_PROVIDER}" != "google" ]; then
#   echo -e "${DNS_PROVIDER_CREDENTIALS}" > /dns_api_key.ini
#   dns_provider_options="${dns_provider_options} --dns-${DNS_PROVIDER}-credentials /dns_api_key.ini"
# fi

# echo certbot command: certbot certonly -n \
#   -m "${LETSENCRYPT_CONTACT_EMAIL}" --agree-tos \
#   --preferred-challenges dns ${dns_provider_options} \
#   -d "*.${CUSTOM_DOMAIN}"

# certbot certonly -n \
#   -m "${LETSENCRYPT_CONTACT_EMAIL}" --agree-tos \
#   --preferred-challenges dns ${dns_provider_options} \
#   -d "*.${CUSTOM_DOMAIN}"

# echo "Convert private key into RSA format"
# openssl rsa \
#   -in "/etc/letsencrypt/live/${CUSTOM_DOMAIN}/privkey.pem" \
#   -out "/etc/letsencrypt/live/${CUSTOM_DOMAIN}/privkey-rsa.pem" \


# echo "Backup of letsencrypt context"
# gsutil -m rsync -r /etc/letsencrypt "${LETSENCRYPT_BUCKET}"

# echo "Install certificate on App Engine"
# certificate_id=24364635
# echo "Found existing certificate : ${certificate_id}"



# echo ""
# echo "CERTIFICATE LOGGED 1"
# echo "/etc/letsencrypt/live/${CUSTOM_DOMAIN}/fullchain.pem"
# echo ""
# cat /etc/letsencrypt/live/${CUSTOM_DOMAIN}/fullchain.pem
# echo "🏁"
# echo ""

# echo ""
# echo "PRIVATE KEY LOGGED 1"
# echo "/etc/letsencrypt/live/${CUSTOM_DOMAIN}/privkey-rsa.pem"
# echo ""
# cat /etc/letsencrypt/live/${CUSTOM_DOMAIN}/privkey-rsa.pem
# echo "🏁"
# echo ""

# echo ""
# echo "CERTIFICATE LOGGED 2"
# echo ""
# cat /etc/letsencrypt/live/shopinzon.com-0005/fullchain.pem
# echo "🏁"
# echo ""

# echo ""
# echo "PRIVATE KEY LOGGED 2"
# echo ""
# cat /etc/letsencrypt/live/shopinzon.com-0005/privkey.pem
# echo "🏁"
# echo ""


# if [ "${certificate_id}" = "" ]; then
#   echo "Creating new certificate"
#   certificate_id=$(gcloud app ssl-certificates create \
#     --display-name "${CERTIFICATE_NAME}" \
#     --certificate "/etc/letsencrypt/live/${CUSTOM_DOMAIN}/fullchain.pem" \
#     --private-key "/etc/letsencrypt/live/${CUSTOM_DOMAIN}/privkey-rsa.pem" \
#     --format "get(id)")
# else
#   echo "Updating existing certificate"
#   gcloud app ssl-certificates update "${certificate_id}" \
#     --certificate "/etc/letsencrypt/live/${CUSTOM_DOMAIN}/fullchain.pem" \
#     --private-key "/etc/letsencrypt/live/${CUSTOM_DOMAIN}/privkey-rsa.pem"
# fi

# echo "Enable certificate on *.${CUSTOM_DOMAIN} domain mapping"
# gcloud app domain-mappings update "*.${CUSTOM_DOMAIN}" --certificate-management manual --certificate-id "${certificate_id}"
