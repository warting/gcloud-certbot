/**
 * run node generateDnsCredential.js
 * The script will ask for the following information:
 * - the name of the dns (default "ovh")
 * - the dns api endpoint (e.g. "ovh-eu")
 * - the applicationKey
 * - the applicationSecret
 * - the consumerKey
 * For ovh, you can generate the credentials by visiting:
 * https://eu.api.ovh.com/createApp/
 */

const { Node } = require('graph-fs');
const rl = require('readline').createInterface({
	input: process.stdin,
	output: process.stdout
});

function ask(title, defaultValue) {
	return new Promise(resolve =>
		rl.question(
			title + (defaultValue ? ` ( ${defaultValue} )` : ""),
			input => resolve(input || defaultValue)
		)
	);
}

function generate({
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


async function main() {
	console.log('Before, generate credentials for dns at https://eu.api.ovh.com/createApp/');

	const steps = [
		// [ question title, output key, default value ]
		["What is your dns?", "dns", "ovh"],
		["What is the dns' api endpoint?", "dnsEndpoint", "ovh-eu"],
		["Paste the application key: ", "applicationKey"],
		["Paste the application secret: ", "applicationSecret"],
		["Paste the application consumer key: ", "consumerKey"],
	];

	const inputs = {};
	for (let [title, key, defaultValue] of steps)
		inputs[key] = await ask(title, defaultValue);

	const DNS_PROVIDER_CREDENTIALS = generate(inputs);
	const json = JSON.stringify({ DNS_PROVIDER_CREDENTIALS }, null, 4);
	new Node(__dirname)
		.resolve('output/dns-credential.json')
		.overwrite(json);

	console.log("✅ Open ./output/dns-credential.json. The key is the environment key you need to set.")
}

main();