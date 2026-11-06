> Unedited output of `python main.py samples/vendor_rollout_plan.md`, run on 2026-11-06 with `qwen3:8b` served locally through `NEBIUS_BASE_URL` (an OpenAI-compatible endpoint), not on Nebius Token Factory.
> This small local model made errors the default model may not:
> the summary is a title only;
> SEC-1 says the export is unencrypted, which the sample never states, and issue 3 and LEG-4 repeat that claim;
> issue 4's reasoning misreads OPS-6 and says there is no 90-day cancellation window, which the sample has;
> issue 8's reasoning misstates the levels of OPS-2 and OPS-3;
> SEC-5's evidence quote is cut off.
> The Validation warnings section shows the report check flagging issue 8 as rated below its most severe finding, and five findings the coordinator left out.

# Risk Review Report

Risk Review Board Report

## Issues

### 1. Data Transfer Without Data Processing Agreement (DPA) (CRITICAL)

- **Sources:** LEG-1, SEC-1, SEC-3
- **Reasoning:** LEG-1, SEC-1, and SEC-3 all identify the absence of a DPA for data transfers to the US. LEG-1 and SEC-1 rate this as critical, while SEC-3 rates it as medium. The critical rating from LEG-1 and SEC-1 takes precedence due to the regulatory and compliance risks under GDPR/CCPA. The combined risk level remains critical.
- **Recommendation:** Finalize the DPA before go-live and ensure it includes appropriate data protection clauses and liability terms.

### 2. Lack of Explicit Consent for Data Use (CRITICAL)

- **Sources:** LEG-2, SEC-5
- **Reasoning:** LEG-2 and SEC-5 both highlight the absence of explicit customer consent for data use. LEG-2 rates this as critical, while SEC-5 rates it as medium. The critical rating from LEG-2 takes precedence due to the legal and reputational risks of unauthorized data usage. The combined risk level remains critical.
- **Recommendation:** Require Quillmark to provide detailed data usage policies and ensure they align with privacy expectations before deployment.

### 3. Unencrypted Data in Transit (CRITICAL)

- **Sources:** SEC-1
- **Reasoning:** SEC-1 identifies the lack of TLS encryption for data in transit as a critical risk. This exposes sensitive customer data to interception. The critical risk level is maintained.
- **Recommendation:** Implement TLS encryption for all data in transit and confirm encryption at rest for data stored by Quillmark.

### 4. Auto-Renewal Without Cancellation Notice (HIGH)

- **Sources:** FIN-2, OPS-6
- **Reasoning:** FIN-2 and OPS-6 both identify the 3-year auto-renewal clause without a 90-day cancellation window as a high-risk issue. While LEG-3 also mentions auto-renewal, its lower rating (medium) is overridden by the higher risk of continued commitment without explicit approval. The combined risk level remains high.
- **Recommendation:** Negotiate a shorter auto-renewal term or establish a formal process for reviewing and terminating the contract before renewal.

### 5. Limited Liability Cap and No Service Credits (HIGH)

- **Sources:** FIN-3, LEG-3, SEC-3
- **Reasoning:** FIN-3, LEG-3, and SEC-3 all highlight the inadequate liability cap (one month of fees) and lack of service credits. LEG-3 and SEC-3 rate this as medium, but FIN-3's high rating takes precedence due to the greater financial exposure from potential breaches or service failures. The combined risk level remains high.
- **Recommendation:** Request a higher liability cap or negotiate for service credits in the contract terms.

### 6. Shared API Key with Broad Permissions (HIGH)

- **Sources:** SEC-2
- **Reasoning:** SEC-2 identifies the use of a single API key with billing/user account permissions as a high-risk issue. This represents a significant attack surface if compromised. No conflicting ratings, so the high risk level remains unchanged.
- **Recommendation:** Use separate API keys for different functions, rotate keys regularly, and store them in secure secret management systems.

### 7. Insufficient Rollback and Incident Response (HIGH)

- **Sources:** OPS-1, SEC-4
- **Reasoning:** OPS-1 and SEC-4 both highlight the lack of a rollback plan and on-call ownership. OPS-1 rates this as high, while SEC-4 also rates it as high. The combined risk level remains high.
- **Recommendation:** Implement feature flags for staged rollouts, define a rollback plan, and assign an on-call owner for incident response.

### 8. Insufficient Monitoring and On-Call Ownership (HIGH)

- **Sources:** OPS-2, OPS-3
- **Reasoning:** OPS-2 and OPS-3 both identify gaps in monitoring frequency and on-call ownership. OPS-2 rates this as high, while OPS-3 also rates it as high. The combined risk level remains high.
- **Recommendation:** Establish real-time monitoring protocols and assign dedicated on-call owners for the integration.

### 9. Budget Gap for Cloud Data Transfer Costs (MEDIUM)

- **Sources:** FIN-1, OPS-4
- **Reasoning:** Both FIN-1 and OPS-4 highlight the absence of data transfer costs in the budget. The 400 GB nightly export could lead to significant financial exposure if cloud pricing changes or data volume increases. While FIN-1 rates this as medium, OPS-4 also identifies it as medium, so the combined risk level remains medium.
- **Recommendation:** Include data transfer costs in the budget and evaluate compression/segmentation strategies to reduce bandwidth usage.

### 10. Third-Party Data Use Without Transparency (MEDIUM)

- **Sources:** SEC-5
- **Reasoning:** SEC-5 highlights the lack of transparency about how Quillmark uses exported data. This creates uncertainty about data misuse risks. The medium risk level is maintained.
- **Recommendation:** Require Quillmark to provide detailed data usage policies and ensure they align with privacy expectations before deployment.

## Validation warnings

- Issue 'Insufficient Monitoring and On-Call Ownership' is rated high, below its most severe finding (critical); check its reasoning.
- No issue cites FIN-4 (Unverified Assumption of 12% AOV Lift); see the original findings.
- No issue cites FIN-5 (Missing Data Processing Agreement); see the original findings.
- No issue cites LEG-4 (Insufficient Data Security Measures); see the original findings.
- No issue cites LEG-5 (Unaddressed Regulatory Compliance for Data Transfers); see the original findings.
- No issue cites OPS-5 (Limited Vendor Support Coverage); see the original findings.

## Original findings

### Security Reviewer

- **SEC-1** Data Exposure via Unencrypted Nightly Export (critical)
  - Evidence: "The nightly export job sends full customer order history (names, emails, shipping addresses, and order history since 2019) to Quillmark's US-hosted API without mentioning encryption in transit. The document states: 'the nightly export job that sends the full customer order history to Quillmark's hosted API in the United States' but does not describe encryption for data in transit."
  - Reasoning: Sending sensitive customer data without encryption in transit exposes it to interception and unauthorized access. The lack of encryption is a critical risk for data confidentiality and compliance with data protection regulations like GDPR or CCPA if customers are in jurisdictions requiring such safeguards.
  - Recommendation: Implement TLS encryption for all data in transit and confirm encryption at rest for data stored by Quillmark.
- **SEC-2** Shared API Key with Broad Permissions (high)
  - Evidence: "The export job and widget both use 'one Quillmark admin API key, which also manages billing and user accounts.' The key is 'pasted in the team wiki so any engineer can debug the integration' and 'no plan to rotate the key.'"
  - Reasoning: A single API key with billing/user account permissions represents a significant attack surface. If compromised, it could allow unauthorized access to financial systems and user data. Storing secrets in a shared wiki and lack of rotation increase exposure risks.
  - Recommendation: Use separate API keys for different functions (widget vs. export), rotate keys regularly, and store them in secure secret management systems (e.g., Vault) rather than shared documentation.
- **SEC-3** Lack of Data Processing Agreement (medium)
  - Evidence: "No data processing agreement has been requested; legal review is scheduled after go-live. The document states: 'No data processing agreement has been requested; legal review is scheduled after go-live.'"
  - Reasoning: Without a data processing agreement, there is no enforceable contract ensuring Quillmark will handle customer data securely or comply with data protection laws. This creates legal and reputational risks if data is mishandled.
  - Recommendation: Finalize a data processing agreement (DPA) before go-live to ensure compliance with data protection regulations and define responsibilities for data handling.
- **SEC-4** Insufficient Rollback and Incident Response (high)
  - Evidence: "There is 'no feature flag and no rollback plan; removing the widget needs a full site deploy.' Additionally, 'no on-call owner has been named for the integration.'"
  - Reasoning: The lack of a rollback plan and on-call owner increases the attack surface and operational risk. If the widget causes issues or a breach, the team cannot quickly disable it, leading to prolonged exposure of customer data.
  - Recommendation: Implement feature flags for staged rollouts, define a rollback plan, and assign an on-call owner for incident response.
- **SEC-5** Third-Party Data Use Without Transparency (medium)
  - Evidence: "Quillmark may use the exported data 'to improve its models across customers,' per its standard terms. The document states: 'Quillmark may use the exported data "
  - Reasoning: The lack of transparency about how Quillmark uses the data (e.g., for model training) creates uncertainty about data misuse risks. Without clear contractual terms, there is no enforceable mechanism to prevent unintended data exploitation.
  - Recommendation: Require Quillmark to provide detailed data usage policies and ensure they align with privacy expectations before deployment.

### Legal Reviewer

- **LEG-1** Data Transfer Without Data Processing Agreement (DPA) (critical)
  - Evidence: "The nightly export sends customer data (names, emails, addresses, order history) to Quillmark's US-hosted API. No data processing agreement has been requested, and the document states 'legal review is scheduled after go-live'."
  - Reasoning: Under GDPR and other privacy laws, transferring personal data to countries without adequacy decisions (like the US) requires a DPA. The absence of this agreement exposes Fernway to regulatory violations and liability if data is mishandled.
  - Recommendation: Negotiate a DPA with Quillmark before go-live to ensure compliance with data protection laws.
- **LEG-2** Lack of Explicit Consent for Data Use (critical)
  - Evidence: "Quillmark may use exported data 'to improve its models across customers', but there is no mention of obtaining explicit consent from customers for this purpose."
  - Reasoning: GDPR and similar laws require explicit consent for processing personal data for purposes like personalization. Without consent, this use of data could violate privacy regulations.
  - Recommendation: Obtain explicit customer consent for data sharing and document it in the privacy policy.
- **LEG-3** Limited Liability Cap (medium)
  - Evidence: "Quillmark's liability is capped at 'one month of fees' with no service credits. The contract auto-renews for 3 years unless cancelled 90 days in advance."
  - Reasoning: A one-month liability cap is insufficient for potential breaches or service failures. The auto-renewal clause also creates long-term obligations without clear termination rights.
  - Recommendation: Negotiate higher liability caps and include service credits for downtime or data breaches.
- **LEG-4** Insufficient Data Security Measures (medium)
  - Evidence: "The Quillmark admin API key is stored in the team wiki, accessible to any engineer, and there is no plan to rotate it. The nightly export involves 400 GB of data."
  - Reasoning: Exposing API credentials in a shared wiki increases the risk of unauthorized access. The lack of key rotation and data encryption during transfer could lead to data breaches.
  - Recommendation: Implement strict access controls, rotate the API key, and encrypt data in transit and at rest.
- **LEG-5** Unaddressed Regulatory Compliance for Data Transfers (medium)
  - Evidence: "The document notes the data is sent to a US-hosted API but does not address regulatory requirements for cross-border data transfers (e.g., GDPR, CCPA)."
  - Reasoning: Failure to comply with cross-border data transfer regulations could result in fines or legal action, especially if customers are in jurisdictions with strict privacy laws.
  - Recommendation: Conduct a privacy impact assessment and ensure compliance with all applicable data protection laws.

### Finance Reviewer

- **FIN-1** Budget Gap for Cloud Data Transfer Costs (medium)
  - Evidence: "The budget covers the license only. Our cloud provider charges for data leaving our network, and the nightly export is about 400 GB."
  - Reasoning: The document explicitly states that cloud data transfer costs are not included in the budget, creating a potential financial gap. The 400 GB nightly export could result in significant unexpected expenses depending on the cloud provider's pricing structure.
  - Recommendation: Include an estimate for cloud data transfer costs in the budget and monitor usage post-deployment.
- **FIN-2** Auto-Renewal Without Cancellation Notice (high)
  - Evidence: "Quillmark's standard order form: a 3-year term that auto-renews for another 3 years unless cancelled in writing 90 days before the end of the term."
  - Reasoning: The auto-renewal clause creates a high risk of continued commitment without explicit approval. The 90-day cancellation window may be insufficient to manage the contract if the service fails to meet expectations or if costs increase.
  - Recommendation: Negotiate a shorter auto-renewal term or establish a formal process for reviewing and potentially terminating the contract before renewal.
- **FIN-3** Limited Liability Cap (high)
  - Evidence: "Quillmark's liability is capped at one month of fees. There are no service credits."
  - Reasoning: The liability cap of one month's fees is inadequate for potential service disruptions or data breaches. The absence of service credits means no financial compensation for performance failures, increasing financial exposure.
  - Recommendation: Request a higher liability cap or negotiate for service credits in the contract terms.
- **FIN-4** Unverified Assumption of 12% AOV Lift (high)
  - Evidence: "The business case assumes a 12% lift in average order value, based on Quillmark's marketing material."
  - Reasoning: The 12% lift assumption is based solely on Quillmark's marketing claims without any supporting data or validation. This creates a high risk that the projected savings will not materialize, undermining the business case.
  - Recommendation: Require Quillmark to provide evidence or a pilot study demonstrating the 12% lift before committing to the contract.
- **FIN-5** Missing Data Processing Agreement (high)
  - Evidence: "No data processing agreement has been requested; legal review is scheduled after go-live."
  - Reasoning: The absence of a data processing agreement (DPA) exposes the company to regulatory risks, particularly under GDPR or other data protection laws. Without a DPA, the company may not have legal safeguards for data transfers to the U.S., increasing compliance and financial exposure.
  - Recommendation: Finalize the DPA before go-live and ensure it includes appropriate data protection clauses and liability terms.

### Operations Reviewer

- **OPS-1** No Rollback Plan (high)
  - Evidence: "There is no feature flag and no rollback plan; removing the widget needs a full site deploy."
  - Reasoning: A full site deploy to rollback during peak traffic (Black Friday week) introduces high operational risk and potential downtime if issues arise post-launch. No mechanism to quickly disable the widget without a deploy increases the risk of prolonged outages or data issues.
  - Recommendation: Implement a feature flag for the widget and define a rollback plan with clear steps for disabling the widget without a full deploy.
- **OPS-2** Insufficient Monitoring Frequency (medium)
  - Evidence: "The team will check Quillmark's dashboard weekly."
  - Reasoning: Weekly dashboard checks may not detect critical failures or performance issues in real time, especially during high-traffic periods like Black Friday. This could delay incident response and impact customer experience.
  - Recommendation: Increase monitoring frequency to daily checks or integrate real-time alerts for critical metrics (e.g., API errors, latency, data export failures).
- **OPS-3** No On-Call Ownership (critical)
  - Evidence: "No on-call owner has been named for the integration. The team will check Quillmark's dashboard weekly."
  - Reasoning: The absence of an on-call owner leaves the integration without dedicated responsibility for incident response, especially during non-business hours. Quillmark's support is only available weekdays, creating a gap in coverage for critical issues outside this window.
  - Recommendation: Assign an on-call owner for the integration and define escalation procedures for vendor-related incidents.
- **OPS-4** Unaccounted Data Transfer Costs (medium)
  - Evidence: "The budget covers the license only. Our cloud provider charges for data leaving our network, and the nightly export is about 400 GB."
  - Reasoning: The 400 GB nightly export could incur significant data transfer costs, which are not included in the budget. This creates financial risk if the data volume grows or if the cloud provider's pricing changes.
  - Recommendation: Include data transfer costs in the budget and evaluate compression/segmentation strategies to reduce bandwidth usage.
- **OPS-5** Limited Vendor Support Coverage (medium)
  - Evidence: "Quillmark support is available on weekdays, 9am to 5pm Pacific time."
  - Reasoning: Support is only available during business hours, which may not align with peak traffic or incident timelines (e.g., Black Friday). This limits the ability to resolve issues promptly during critical periods.
  - Recommendation: Confirm extended support hours or establish a dedicated support SLA with Quillmark for mission-critical periods.
- **OPS-6** Vendor Liability and Legal Gaps (high)
  - Evidence: "Quillmark's liability is capped at one month of fees. There are no service credits. No data processing agreement has been requested; legal review is scheduled after go-live."
  - Reasoning: The data export includes sensitive customer information (names, addresses, order history), but no data processing agreement is in place. The liability cap and lack of legal review before go-live expose the organization to potential data breaches or compliance risks.
  - Recommendation: Finalize the data processing agreement with Quillmark before go-live and ensure liability terms align with regulatory requirements (e.g., GDPR, CCPA).
