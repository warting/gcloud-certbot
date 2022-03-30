/**
 * The script will create a json file with all environment variables 
 * you should set for the container using ovh.
 * output: ./output/env-vars.json
 * 
 * Before running the script, get ovh credentials, 
 * go to https://eu.api.ovh.com/createToken 
 * and create credentials with all methods permitted to "/domain/zone/*"
 * Related links 
 * 	https://certbot-dns-ovh.readthedocs.io/en/stable/
 */

const { Node } = require('graph-fs');
const rl = require('readline').createInterface({
	input: process.stdin,
	output: process.stdout
});


async function main() {
	console.log('Before, generate credentials for dns at https://eu.api.ovh.com/createApp/');

	const steps = [
		// [ question title, output key, default value ]
		["What is your domain?", "domain"],
		["What is your dns?", "dns", "ovh"],
		["What is the dns' api endpoint?", "dnsEndpoint", "ovh-eu"],
		["Paste the application key:", "applicationKey"],
		["Paste the application secret:", "applicationSecret"],
		["Paste the application consumer key:", "consumerKey"],
		["What's your contact email? (for Let's Encrypt)", "contactEmail"],
	];

	const inputs = {};
	for (let [title, key, defaultValue] of steps)
		inputs[key] = await ask(title, defaultValue);

	const DNS_PROVIDER_CREDENTIALS = envProviderCredential(inputs);

	const json = JSON.stringify({
		CUSTOM_DOMAIN: inputs.domain,
		DNS_PROVIDER: inputs.dns,
		LETSENCRYPT_CONTACT_EMAIL: inputs.contactEmail,
		DNS_PROVIDER_CREDENTIALS,
		CERTIFICATE_ID: inputs.certificatId,
	}, null, 4);

	new Node(__dirname)
		.resolve('output/env-vars.json')
		.overwrite(json);

	console.log("✅ Open ./output/dns-credential.json. The key is the environment key you need to set.")
	process.exit(0);
}

main();

// ---

function ask(title, defaultValue) {
	return new Promise(resolve =>
		rl.question(
			title + (defaultValue ? ` ( ${defaultValue} )` : "") + '\t',
			input => resolve(input || defaultValue)
		)
	);
}

function envProviderCredential({
	dns, dnsEndpoint,
	applicationKey, applicationSecret,
	consumerKey
}) {
	return [
		[`dns_${dns}_endpoint`, dnsEndpoint],
		[`dns_${dns}_application_key`, applicationKey],
		[`dns_${dns}_application_secret`, applicationSecret],
		[`dns_${dns}_consumer_key`, consumerKey],
	]
		.map(x => x.join("="))
		.join('\n');
}