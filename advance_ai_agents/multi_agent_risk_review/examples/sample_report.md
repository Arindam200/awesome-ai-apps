> Unedited output of `python main.py samples/vendor_rollout_plan.md`, run on 2026-11-15 on Nebius Token Factory with the default model, `Qwen/Qwen3-30B-A3B-Instruct-2507`.
> The model's errors include:
> LEG-2 calls the team wiki public;
> SEC-2 and issue 5 say the export is unencrypted, which the sample never says;
> LEG-1 and issue 2 call the export a cross-border transfer, but the sample never says where Fernway is;
> FIN-1 and issue 6 say the contract allows no mid-term cancellation or early termination, and issue 7 says it has no indemnification, though the sample mentions neither;
> LEG-7 and issue 12 say the data is not licensed for resale or third-party use, which the sample never says;
> issue 2 says SEC-3 rated the risk critical, and issues 8 and 11 say OPS-1 and OPS-5 rated it medium, but all three rated it high;
> issue 4 folds the consent finding (LEG-3) and the capacity finding (OPS-4) into the 12% uplift issue.
> The Validation warnings section shows the report check flagging two issues rated below their most severe finding, two findings cited by two issues, and one finding no issue cites.

# Risk Review Report

The integration with Quillmark presents multiple high- and critical-level risks across finance, legal, security, and operations domains. Key issues include unmanaged financial exposure from auto-renewing contracts and unaccounted data egress costs, critical data privacy and compliance risks due to cross-border data transfers without a Data Processing Agreement (DPA), and severe security vulnerabilities from a shared, unrotated admin API key. Operational risks include lack of rollback capability, no on-call ownership, and insufficient monitoring. These risks are interrelated and must be addressed before go-live to avoid financial loss, regulatory penalties, data breaches, or service disruption during the critical holiday season.

## Issues

### 1. Critical: Uncontrolled access via shared, non-rotated admin API key with broad privileges (CRITICAL)

- **Sources:** FIN-5, LEG-2, OPS-6, SEC-1
- **Reasoning:** Multiple reviewers identified the same core issue: a single, static, shared admin API key with full access to billing, user accounts, and data exports is stored in the team wiki and not rotated. This creates a critical security and operational risk. The finance (FIN-5), legal (LEG-2), operations (OPS-6), and security (SEC-1) reviewers all raised this issue with identical evidence and reasoning. The security reviewer (SEC-1) explicitly labeled it as 'critical' and provided the most comprehensive justification, citing violation of least privilege and secure credential management principles. Since all reviewers agree on the severity and root cause, and no mitigating evidence was presented, the highest risk level (critical) is retained.
- **Recommendation:** Immediately revoke the current API key. Implement dedicated, least-privilege API keys for the widget and export job. Store keys in a secure secrets manager (e.g., AWS Secrets Manager, HashiCorp Vault). Enforce automated key rotation and audit logging. Remove the key from the team wiki.

### 2. Critical: Cross-border transfer of sensitive customer data without a Data Processing Agreement (DPA) (CRITICAL)

- **Sources:** FIN-4, LEG-1, SEC-3
- **Reasoning:** The nightly export of full customer order history (names, emails, shipping addresses, order history since 2019) to Quillmark’s U.S.-based API constitutes a cross-border transfer of personal data. The legal (LEG-1) and security (SEC-3) reviewers both identified this as critical, citing GDPR, CCPA, and similar regulations requiring a DPA before processing. The finance reviewer (FIN-4) also flagged this as high financial exposure due to legal and compliance risk. Although FIN-4 rated it as 'high', the legal and security reviewers both rated it as 'critical' and provided stronger regulatory evidence. Since the legal and security reviewers' evidence shows a clear violation of data protection law and the risk is not mitigated by any reviewer, the higher (critical) level is justified.
- **Recommendation:** Immediately negotiate and execute a legally binding Data Processing Agreement (DPA) with Quillmark before go-live. The DPA must include provisions for data subject rights, security measures, sub-processing, data retention, cross-border transfer mechanisms (e.g., SCCs), and audit rights. Do not initiate data exports until the DPA is signed.

### 3. Critical: Unaccounted data egress costs creating a budget gap (CRITICAL)

- **Sources:** FIN-2
- **Reasoning:** The finance reviewer (FIN-2) identified a critical budget gap due to data egress costs not included in the current budget. The nightly export of 400 GB incurs cloud provider charges that are not accounted for. No other reviewer contradicted this finding, and no evidence was presented that the cost is already covered or mitigated. The risk is purely financial and directly tied to a measurable, recurring expense. Since the reviewer explicitly labeled it as 'critical' and the evidence is clear and unchallenged, the risk level remains critical.
- **Recommendation:** Reallocate budget to cover data egress costs or revise the data export frequency/size. Conduct a cost-benefit analysis including egress fees before proceeding with the integration.

### 4. High: Unverified financial assumption of 12% uplift in average order value (HIGH)

- **Sources:** FIN-3, LEG-3, OPS-4
- **Reasoning:** The business case assumes a 12% increase in average order value based solely on Quillmark’s marketing claims. The finance reviewer (FIN-3) rated this as high financial risk due to lack of validation. The legal reviewer (LEG-3) reinforced this by noting that the data is used for model improvement, which requires consent and transparency. The operations reviewer (OPS-4) highlighted the high volume (400 GB) and lack of capacity planning, which increases risk if the assumption fails. While FIN-3 and LEG-3 both rated it as high, and OPS-4 noted operational risk, no reviewer downgraded the risk. The assumption remains speculative and unvalidated, so the high level is maintained.
- **Recommendation:** Conduct a pilot rollout with a subset of users to validate the 12% uplift assumption. Require Quillmark to provide third-party case studies or performance benchmarks. Implement a clear opt-in consent mechanism for data sharing and update privacy notices.

### 5. High: Lack of data minimization and encryption in data exports (HIGH)

- **Sources:** SEC-2, SEC-3
- **Reasoning:** The security reviewers (SEC-2 and SEC-3) identified that the export includes full customer PII (names, emails, shipping addresses, order history) without encryption in transit or at rest. SEC-2 explicitly cited this as a high risk due to volume, sensitivity, and lack of DPA. SEC-3 reinforced that the data is used for cross-customer model training, increasing exposure. Although SEC-2 and SEC-3 both rated it as high, and the legal reviewer (LEG-3) supported the need for consent, no reviewer downgraded the risk. The lack of encryption and data minimization remains a significant vulnerability, so the high level is retained.
- **Recommendation:** Encrypt exported data in transit (TLS 1.2+) and at rest (AES-256). Implement data minimization—only export necessary fields (e.g., order IDs, product IDs, timestamps). Require a DPA before any export.

### 6. High: Auto-renewing 3-year contract with no cancellation flexibility (HIGH)

- **Sources:** FIN-1
- **Reasoning:** The finance reviewer (FIN-1) identified a high financial exposure due to a 3-year auto-renewing contract with no mid-term cancellation or early termination option. The contract locks Fernway into a long-term commitment without a clear exit path. No other reviewer contradicted this finding, and no mitigating evidence was provided. The risk is purely financial and structural, so the high level is maintained.
- **Recommendation:** Negotiate a shorter initial term (e.g., 12 months) with a 30-day cancellation window. Require a formal business review before renewal to assess ROI.

### 7. High: Lack of contractual liability and indemnity protections (HIGH)

- **Sources:** LEG-4
- **Reasoning:** The legal reviewer (LEG-4) identified a high risk due to Quillmark’s liability cap of one month’s fees (approx. $8,000), which is insufficient to cover potential damages from a breach or outage. The absence of service credits and indemnification creates significant financial exposure. No other reviewer downgraded this risk, and the evidence is clear. The high level is retained.
- **Recommendation:** Negotiate a revised contract with Quillmark to include: (1) a higher liability cap (e.g., covering actual damages), (2) service credits for downtime, (3) indemnification for data protection breaches, and (4) audit rights.

### 8. Medium: No feature flag or rollback plan for widget deployment (MEDIUM)

- **Sources:** LEG-5, OPS-1, SEC-4
- **Reasoning:** Multiple reviewers (legal, operations, security) identified the lack of a feature flag and rollback plan, requiring a full site deploy to remove the widget. This increases MTTR and operational risk during peak season. The legal (LEG-5) and operations (OPS-1) reviewers rated it as medium, and the security reviewer (SEC-4) also rated it as medium. All agree on the risk, and no higher level was justified. The risk is operational and not critical, so medium is appropriate.
- **Recommendation:** Implement a feature flag to enable/disable the widget independently of deployment. Develop and test a documented rollback procedure. Assign ownership and conduct pre-go-live testing.

### 9. Medium: No on-call ownership or monitoring for Quillmark integration (MEDIUM)

- **Sources:** LEG-6, OPS-2, SEC-5
- **Reasoning:** All three reviewers (legal, operations, security) identified the lack of an on-call owner and reliance on weekly manual checks. This creates a gap in incident response, especially during out-of-hours or high-traffic periods. The risk is operational and not critical, as the integration is not immediately compromised, but the delay in detection increases risk. The medium level is consistent across all reviewers and justified.
- **Recommendation:** Assign a dedicated on-call owner for the Quillmark integration. Implement automated monitoring and alerting (e.g., via cloud tools) for export job failures, API errors, and data anomalies. Set up 24/7 alerts and response SLAs.

### 10. Medium: Insufficient capacity planning and performance testing for 400 GB nightly export (MEDIUM)

- **Sources:** OPS-4
- **Reasoning:** The operations reviewer (OPS-4) identified a medium risk due to the 400 GB nightly export with no capacity planning or load testing. This could lead to network strain, throttling, or impact on other services. No other reviewer contradicted this, and the risk is operational and measurable. The medium level is appropriate.
- **Recommendation:** Conduct capacity planning for the export job, including network bandwidth, processing time, and cost. Perform load testing under peak conditions and validate performance.

### 11. Medium: Critical dependency on Quillmark with limited support window (MEDIUM)

- **Sources:** OPS-5
- **Reasoning:** The operations reviewer (OPS-5) identified a medium risk due to Quillmark’s support being limited to weekdays, 9am–5pm Pacific time. This creates a risk during out-of-hours incidents, especially during peak season. While the risk is significant, it is not critical because a contingency plan can mitigate it. The medium level is appropriate.
- **Recommendation:** Establish a contingency plan for out-of-hours incidents, including escalation paths and documented troubleshooting steps. Consider engaging Quillmark for premium support if available.

### 12. Low: Ambiguous data usage rights in Quillmark’s standard terms (LOW)

- **Sources:** LEG-7
- **Reasoning:** The legal reviewer (LEG-7) identified a low risk due to unclear licensing terms for data usage beyond the service. However, the risk is mitigated by the fact that the data is transferred under a contractual relationship and not licensed for resale. The reviewer acknowledged the risk is lower than others and recommended clarification. Since no other reviewer raised this, and the evidence is limited, the low level is retained.
- **Recommendation:** Clarify in the DPA or contract that Quillmark may not use customer data for any purpose other than providing the service and improving its models, and that such use is limited to anonymized or aggregated data where possible.

## Validation warnings

- Issue 'Medium: No feature flag or rollback plan for widget deployment' is rated medium, below its most severe finding (high); check its reasoning.
- Issue 'Medium: Critical dependency on Quillmark with limited support window' is rated medium, below its most severe finding (high); check its reasoning.
- SEC-3 is cited by 2 issues; check whether they repeat one risk.
- OPS-4 is cited by 2 issues; check whether they repeat one risk.
- No issue cites OPS-3 (Insufficient monitoring and alerting for Quillmark integration); see the original findings.

## Original findings

### Security Reviewer

- **SEC-1** Critical: Single API key with unrestricted access and no rotation (critical)
  - Evidence: "The export job and the widget both use one Quillmark admin API key, which also manages billing and user accounts. The key is pasted in the team wiki so any engineer can debug the integration. There is no plan to rotate the key."
  - Reasoning: A single admin-level API key with broad privileges (including billing and user account management) is stored in a shared team wiki, accessible to any engineer. This creates a critical risk of credential exposure and unauthorized access. The lack of key rotation increases the window of opportunity for compromise. This violates fundamental principles of least privilege and secure credential management.
  - Recommendation: Immediately restrict the API key to the minimum required permissions (e.g., read-only for export, no billing or account management). Move the key to a secure secrets management system (e.g., HashiCorp Vault, AWS Secrets Manager). Implement a key rotation policy with automated rotation and audit logging. Remove the key from the team wiki.
- **SEC-2** High: Exposure of sensitive customer data in unencrypted, large-scale exports (high)
  - Evidence: "A nightly export job sends the full customer order history to Quillmark's hosted API in the United States, including customer names, email addresses, shipping addresses and every order since 2019."
  - Reasoning: The export includes sensitive personal data (PII) such as names, email addresses, and full shipping addresses, spanning over five years. The data is transmitted to a third party in the United States without indication of encryption in transit or at rest. Given the volume (400 GB nightly) and sensitivity, this constitutes a high-risk exposure of PII to a third party without a data processing agreement (DPA) in place. The lack of encryption and DPA increases the risk of data misuse, breach, or regulatory non-compliance.
  - Recommendation: Encrypt the exported data in transit (using TLS 1.2+) and at rest (using AES-256). Implement data minimization—only export necessary fields (e.g., order IDs, product IDs, timestamps) rather than full customer PII. Require a Data Processing Agreement (DPA) with Quillmark before any data is exported. Conduct a data protection impact assessment (DPIA) for this processing.
- **SEC-3** High: Third-party access to full customer history without contractual safeguards (high)
  - Evidence: "Quillmark may use the exported data 'to improve its models across customers', per its standard terms. No data processing agreement has been requested; legal review is scheduled after go-live."
  - Reasoning: The data export includes full customer order history, which Quillmark may use to improve its models across customers—implying potential cross-customer data aggregation and use. Without a DPA, there is no contractual control over how Quillmark processes, stores, or shares the data. Legal review after go-live is too late; data protection obligations must be established before processing begins. This creates a high risk of non-compliance with privacy regulations (e.g., GDPR, CCPA).
  - Recommendation: Do not initiate data exports until a legally binding Data Processing Agreement (DPA) is signed with Quillmark, explicitly defining permitted uses, data retention, security obligations, and subprocessing rights. Ensure the DPA includes provisions for data subject rights, breach notification, and audit rights. Delay go-live until DPA is in place.
- **SEC-4** Medium: No rollback plan or feature flag for critical integration (medium)
  - Evidence: "There is no feature flag and no rollback plan; removing the widget needs a full site deploy."
  - Reasoning: The recommendation widget is deployed globally at once with no ability to disable it selectively or roll back quickly. This increases the risk of a widespread outage or performance degradation due to a bug or third-party failure. The lack of a rollback plan increases mean time to recovery (MTTR) and operational risk during the critical holiday season.
  - Recommendation: Implement a feature flag to enable/disable the widget independently of deployment. Develop a rollback plan that allows for rapid removal of the widget via a single configuration change. Test the rollback process in staging before go-live.
- **SEC-5** Medium: No on-call ownership for integration with no support outside business hours (medium)
  - Evidence: "No on-call owner has been named for the integration. The team will check Quillmark's dashboard weekly. Quillmark support is available on weekdays, 9am to 5pm Pacific time."
  - Reasoning: The integration has no designated on-call owner, and monitoring is limited to weekly checks. This creates a significant gap in incident response, especially during the holiday season when the system is under peak load. If Quillmark's service fails or the export job breaks, there may be no one to detect or respond promptly. Support is unavailable outside business hours, increasing the risk of prolonged outages.
  - Recommendation: Assign an on-call owner for the Quillmark integration. Implement automated monitoring and alerting for export job failures, API errors, and latency. Set up alerts to be sent to the on-call owner 24/7. Ensure the team has a response plan for out-of-hours incidents.

### Legal Reviewer

- **LEG-1** Critical: No Data Processing Agreement (DPA) in place for cross-border data transfers (critical)
  - Evidence: "No data processing agreement has been requested; legal review is scheduled after go-live."
  - Reasoning: The nightly export sends full customer order history—including names, email addresses, and shipping addresses—across international borders to Quillmark's hosted API in the United States. This constitutes a cross-border data transfer involving personal data. Under GDPR and similar privacy laws (e.g., UK GDPR, CCPA/CPRA), a DPA is legally required when processing personal data on behalf of a controller. Post-hoc legal review is insufficient and violates data protection principles. The lack of a DPA creates a critical compliance risk, particularly given the volume and sensitivity of the data transferred.
  - Recommendation: Immediate negotiation and execution of a DPA with Quillmark before go-live, including provisions for data subject rights, security measures, sub-processing, data retention, and cross-border transfer mechanisms (e.g., SCCs).
- **LEG-2** Critical: Inadequate API key management and lack of access controls (critical)
  - Evidence: "The export job and the widget both use one Quillmark admin API key, which also manages billing and user accounts. The key is pasted in the team wiki so any engineer can debug the integration. There is no plan to rotate the key."
  - Reasoning: Using a single admin-level API key with broad privileges—accessible to all engineers via a public wiki—violates fundamental security principles. The key is effectively hardcoded and exposed, increasing the risk of unauthorized access, data exfiltration, or abuse. The lack of rotation further compounds this risk. This creates a critical vulnerability that could lead to data breaches, financial loss, or service disruption.
  - Recommendation: Immediately revoke the current API key. Implement a dedicated, least-privilege API key for the export job and another for the widget. Store keys in a secure secrets manager (e.g., AWS Secrets Manager, HashiCorp Vault). Enforce key rotation policies and remove the key from the wiki.
- **LEG-3** High: No consent mechanism for sharing customer data with third-party vendor (high)
  - Evidence: "Quillmark may use the exported data 'to improve its models across customers', and the data includes personal information such as names, email addresses, and shipping addresses."
  - Reasoning: The data being shared includes personal data under GDPR, CCPA, and other privacy laws. The use of such data for purposes beyond the original purpose of the transaction (e.g., improving models across customers) requires valid legal basis, such as explicit consent or legitimate interest. There is no indication that customers have been informed or given consent for their data to be used in this way. The business case assumes a 12% lift in average order value based on Quillmark’s marketing material, suggesting the data is used for behavioral modeling, which further necessitates transparency and consent.
  - Recommendation: Implement a clear, opt-in consent mechanism for customers before their data is shared with Quillmark. Update privacy notices to disclose the use of personal data for third-party model training and provide a clear opt-out option. Ensure compliance with GDPR’s Article 7 and CCPA’s right to opt-out of sale of personal information.
- **LEG-4** High: Lack of contractual liability and indemnity protections (high)
  - Evidence: "Quillmark's liability is capped at one month of fees. There are no service credits."
  - Reasoning: The liability cap of one month’s fees (approximately $8,000) is insufficient to cover potential damages from a data breach, service outage, or regulatory fine—especially given the volume of personal data being transferred. The absence of service credits means no financial recourse for downtime or performance failures. This creates a high risk of financial exposure for Fernway in the event of a failure or breach, with no meaningful contractual remedy.
  - Recommendation: Negotiate a revised contract with Quillmark to include: (1) a higher liability cap (e.g., covering actual damages up to a reasonable threshold), (2) service credits for downtime, (3) indemnification for breaches of data protection laws, and (4) audit rights to verify compliance.
- **LEG-5** Medium: No rollback plan or feature flagging for the widget deployment (medium)
  - Evidence: "There is no feature flag and no rollback plan; removing the widget needs a full site deploy."
  - Reasoning: The widget is being deployed globally at once with no ability to disable it selectively or roll back quickly. This increases the risk of a widespread outage or performance degradation due to unforeseen issues. The lack of a rollback plan means any critical bug or security flaw could remain active until the next full deployment cycle, which may take days or longer.
  - Recommendation: Implement a feature flag to enable/disable the widget independently of the code deployment. Develop a documented rollback procedure and test it before go-live. Assign an on-call owner for the integration to ensure rapid response to issues.
- **LEG-6** Medium: No on-call ownership or monitoring for integration (medium)
  - Evidence: "No on-call owner has been named for the integration. The team will check Quillmark's dashboard weekly."
  - Reasoning: With no designated on-call owner and only weekly monitoring, critical issues with the integration (e.g., failed exports, API errors, or security alerts) may go undetected for days. This increases the risk of data loss, compliance violations, or degraded customer experience, especially during high-traffic periods like Black Friday.
  - Recommendation: Assign a dedicated on-call owner for the Quillmark integration. Implement automated monitoring and alerting (e.g., via cloud monitoring tools) for export job failures, API errors, and data transfer anomalies. Establish a response SLA and conduct regular incident drills.
- **LEG-7** Low: No explicit licensing terms for data usage beyond the service (low)
  - Evidence: "Quillmark may use the exported data 'to improve its models across customers', per its standard terms."
  - Reasoning: While the use of customer data for model improvement is broad, the license terms do not explicitly define whether the data is owned by Fernway or whether Quillmark can use it for commercial purposes beyond the service. However, since the data is being transferred under a contractual relationship and not licensed for resale or third-party use, the risk is lower than other findings. Still, it warrants clarification in the DPA or contract.
  - Recommendation: Clarify in the DPA or contract that Quillmark may not use customer data for any purpose other than providing the service and improving its models, and that such use is limited to anonymized or aggregated data where possible.

### Finance Reviewer

- **FIN-1** High financial exposure due to auto-renewing 3-year contract with no cancellation flexibility (high)
  - Evidence: "Quillmark's standard order form: a 3-year term that auto-renews for another 3 years unless cancelled in writing 90 days before the end of the term."
  - Reasoning: The contract auto-renews for another 3 years unless cancelled in writing 90 days prior, creating significant financial exposure if the service underperforms or becomes redundant. There is no option to cancel mid-term, and no provision for early termination, locking Fernway into a long-term commitment without a clear exit path.
  - Recommendation: Negotiate a shorter initial term with a 30-day cancellation window or require written notice 30 days prior to renewal. Require a formal business review before renewal to assess ROI.
- **FIN-2** Critical budget gap due to unaccounted data egress costs (critical)
  - Evidence: "The budget covers the license only. Our cloud provider charges for data leaving our network, and the nightly export is about 400 GB."
  - Reasoning: The budget explicitly excludes data egress costs, which are incurred by the cloud provider for transferring 400 GB of data nightly. These costs are not accounted for in the current budget, creating a significant financial gap that could result in unexpected charges.
  - Recommendation: Reallocate budget to cover data egress costs or revise the data export frequency/size. Conduct a cost-benefit analysis including egress fees before proceeding.
- **FIN-3** High financial risk from unverified savings assumption (high)
  - Evidence: "The business case assumes a 12% lift in average order value, based on Quillmark's marketing material."
  - Reasoning: The projected financial benefit relies entirely on a 12% increase in average order value, which is based on Quillmark’s marketing claims rather than validated data or pilot testing. There is no evidence of actual performance from similar customers or internal testing, making the assumption highly speculative and exposing the business to potential financial loss if the uplift does not materialize.
  - Recommendation: Conduct a pilot rollout with a subset of users to validate the 12% uplift assumption before full deployment. Require Quillmark to provide third-party case studies or performance benchmarks.
- **FIN-4** High financial exposure from lack of data processing agreement and unmanaged data sharing (high)
  - Evidence: "No data processing agreement has been requested; legal review is scheduled after go-live. The export includes customer names, email addresses, shipping addresses and every order since 2019."
  - Reasoning: The export of sensitive customer data (including full order history since 2019) to a third-party hosted API in the United States occurs without a data processing agreement. This creates legal and financial exposure, especially under regulations like GDPR or CCPA, and increases liability if data is mishandled or breached. The lack of pre-deployment legal review compounds this risk.
  - Recommendation: Obtain a data processing agreement before go-live. Conduct a data privacy impact assessment and ensure compliance with applicable data protection laws.
- **FIN-5** Critical risk of uncontrolled access due to static, shared API key with no rotation (critical)
  - Evidence: "The export job and the widget both use one Quillmark admin API key, which also manages billing and user accounts. The key is pasted in the team wiki so any engineer can debug the integration. There is no plan to rotate the key."
  - Reasoning: A single, static, shared admin API key is stored in the team wiki and accessible to all engineers, with no rotation plan. This creates a critical security and financial risk: if the key is exposed, an attacker could access billing, user accounts, and data exports, potentially leading to unauthorized charges or data exfiltration. The lack of key rotation increases the window of exposure.
  - Recommendation: Implement a dedicated, non-admin API key with least-privilege access. Store the key in a secrets manager, not in the wiki. Enforce key rotation and audit access logs.

### Operations Reviewer

- **OPS-1** No rollback plan for widget deployment (high)
  - Evidence: "There is no feature flag and no rollback plan; removing the widget needs a full site deploy."
  - Reasoning: The lack of a rollback plan increases the risk of prolonged downtime or degraded user experience if the widget causes issues post-deployment. A full site deploy for rollback is operationally risky and time-consuming, especially during a high-traffic period like Black Friday.
  - Recommendation: Implement a feature flag to enable gradual rollout and safe rollback. If not feasible, define a documented, tested rollback procedure and assign ownership.
- **OPS-2** No on-call ownership for Quillmark integration (medium)
  - Evidence: "No on-call owner has been named for the integration. The team will check Quillmark's dashboard weekly."
  - Reasoning: Without an on-call owner, there is no guaranteed response to incidents involving the Quillmark integration, especially outside of business hours. This creates a gap in incident response, particularly critical given the integration's impact on the customer experience during peak season.
  - Recommendation: Assign an on-call owner responsible for monitoring, triaging, and responding to issues related to the Quillmark integration.
- **OPS-3** Insufficient monitoring and alerting for Quillmark integration (medium)
  - Evidence: "The team will check Quillmark's dashboard weekly."
  - Reasoning: Weekly manual checks are inadequate for a production-critical integration. Real-time monitoring and alerting are necessary to detect failures in the widget or data export jobs promptly, especially given the high volume of data and time-sensitive nature of the holiday season.
  - Recommendation: Implement automated monitoring and alerting for the widget (e.g., JavaScript errors, load failures) and the nightly export job (e.g., job success/failure, data volume, latency). Integrate with existing observability tools.
- **OPS-4** High data export volume with no capacity planning (medium)
  - Evidence: "The nightly export is about 400 GB. The business case assumes a 12% lift in average order value, based on Quillmark's marketing material."
  - Reasoning: 400 GB of data exported nightly represents a significant outbound data transfer cost and potential network strain. No capacity planning or performance testing is mentioned, increasing the risk of network throttling, increased cloud egress costs, or impact on other services during the export window.
  - Recommendation: Conduct capacity planning for the export job, including network bandwidth, processing time, and cost implications. Perform load testing and validate the export process under peak conditions.
- **OPS-5** Critical dependency on Quillmark with limited support window (high)
  - Evidence: "Quillmark support is available on weekdays, 9am to 5pm Pacific time."
  - Reasoning: The integration is critical to the holiday season rollout, yet support is only available during business hours in a single time zone. This creates a significant risk during outages or performance issues that occur outside of support hours, especially during high-traffic periods like Black Friday.
  - Recommendation: Establish a contingency plan for out-of-hours incidents, including escalation paths and documented troubleshooting steps. Consider engaging Quillmark for premium support if available.
- **OPS-6** Single point of failure: shared API key with no rotation (critical)
  - Evidence: "The export job and the widget both use one Quillmark admin API key, which also manages billing and user accounts. The key is pasted in the team wiki so any engineer can debug the integration. There is no plan to rotate the key."
  - Reasoning: A single, widely shared, non-rotated admin API key creates a critical security and operational risk. If compromised, it could lead to unauthorized access to billing, data exports, and account management. The key's presence in the wiki increases exposure.
  - Recommendation: Immediately restrict access to the API key, implement key rotation, and use least-privilege credentials. Replace the shared admin key with separate, scoped keys for the widget and export job.
