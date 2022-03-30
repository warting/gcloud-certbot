1. Build the image (with Google Cloud Build recommended)
2. Deploy the image (to Google Cloud Run recommended)
3. Prepare dns credentials for the next step (for ovh https://eu.api.ovh.com/createToken)
4. Run `node scripts/generateEnvVars.js` to generate the needed environment variables (read `generateEnvVars.js` head comment before).
5. Set environment variables to the deployed container.
6. Call `/renew` to the container's url.