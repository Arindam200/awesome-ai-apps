# Deployment Plan: Quillmark Personalization Rollout

Fernway Outdoor Supply (fictional) plans to add Quillmark's (fictional) product recommendation service to its online store before the holiday season.

## What we are deploying

- Quillmark's recommendation widget on every product page and in the cart.
- A nightly export job that sends the full customer order history to Quillmark's hosted API in the United States, including customer names, email addresses, shipping addresses and every order since 2019.
- Quillmark may use the exported data "to improve its models across customers", per its standard terms.

## Access and credentials

- The export job and the widget both use one Quillmark admin API key, which also manages billing and user accounts.
- The key is pasted in the team wiki so any engineer can debug the integration.
- There is no plan to rotate the key.

## Contract and cost

- Quillmark's standard order form: a 3-year term that auto-renews for another 3 years unless cancelled in writing 90 days before the end of the term.
- Quillmark's liability is capped at one month of fees. There are no service credits.
- No data processing agreement has been requested; legal review is scheduled after go-live.
- License: $8,000 per month, paid annually in advance.
- The budget covers the license only. Our cloud provider charges for data leaving our network, and the nightly export is about 400 GB.
- The business case assumes a 12% lift in average order value, based on Quillmark's marketing material.

## Rollout

- The widget goes live on all storefronts at once on the Monday of the Black Friday week.
- There is no feature flag and no rollback plan; removing the widget needs a full site deploy.
- Quillmark support is available on weekdays, 9am to 5pm Pacific time.
- No on-call owner has been named for the integration. The team will check Quillmark's dashboard weekly.
