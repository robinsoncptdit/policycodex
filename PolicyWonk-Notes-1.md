## 1. Objective Snapshot

The COO mandates all departments to comprehensively review, update, and centralize governing documents (policies, procedures, by-laws) by summer's end, ensuring accurate, current guidance for schools and parishes while maintaining best practices and operational efficiency across the diocese.

## 2. Stakeholder & Role Map

|Role|Responsibilities|
|---|---|
|COO|Overall mandate owner, final approvals (Gate 5), resource allocation|
|Policy Champion|Document ownership per Seven-Gate workflow, drives individual policy through approval|
|Department Lead|Assigns Policy Champions, validates content, manages department timeline|
|Standing Policy Committee|Cross-functional review (Gate 3): HR, Finance, IT, Risk, Mission alignment|
|General Counsel|Legal compliance sign-off (Gate 4)|
|Internal Audit|Compliance and control verification (Gate 4)|
|Document Control Owner|SharePoint maintenance, version control, publication (Gate 7)|
|Schools/Parishes|End users providing feedback during review phase|
|Board/Governance Committee|High-impact policy ratification (Gate 6)|

## 3. Work-Breakdown Table

|Phase|Key Activities|Primary Owner(s)|Inputs/Outputs|Success Metric|
|---|---|---|---|---|
|**Inventory**|• Locate all documents<br>• Upload to SharePoint<br>• Complete tracker entries<br>• Identify gaps per Gate 1|Policy Champions|Inputs: Scattered documents<br>Outputs: Centralized inventory, gap register|100% of documents logged; gaps registered|
|**Review**|• Assess currency<br>• Stakeholder feedback<br>• SME review (Gate 2)<br>• LLM-assisted analysis|Policy Champions + SMEs|Inputs: Current documents<br>Outputs: Red-lined drafts, upvote metrics|All documents reviewed with human/AI scores|
|**Update**|• Draft revisions<br>• Policy Committee review (Gate 3)<br>• Legal review (Gate 4)<br>• Version control|Policy Champions + Committee|Inputs: Review findings<br>Outputs: Version 1.0 documents|≥90% through Gate 4 approval|
|**Approve**|• Executive approval (Gate 5)<br>• Board ratification if needed (Gate 6)<br>• Archive old versions|COO/VPs + Board|Inputs: Compliant drafts<br>Outputs: Approved policies|All critical policies approved|
|**Publish**|• Upload final versions<br>• Training delivery (Gate 7)<br>• Set review cycles<br>• Track acknowledgments|Document Control Owner|Inputs: Approved documents<br>Outputs: Published policies, training records|100% published with acknowledgments|

## 4. Timeline Draft

**Weeks 1-2** (Starting now):

- Complete inventory phase
- Populate Policy Tracker and gap register
- Assign Policy Champions
- First synchronization meeting

**Weeks 3-4**:

- Review phase with school/parish input
- SME assignments (Gate 2)
- LLM-assisted review deployment

**Weeks 5-6**:

- Complete reviews and red-lines
- Second synchronization meeting
- Prioritize high-impact updates

**Weeks 7-8**:

- Policy Committee reviews (Gate 3)
- Begin legal/compliance reviews (Gate 4)

**Weeks 9-10**:

- Complete Gates 3-4
- Executive approvals (Gate 5)
- Third synchronization meeting

**Weeks 11-12**:

- Board ratification for qualifying policies (Gate 6)
- Publication and training (Gate 7)
- Final synchronization meeting

## 5. Risks & Mitigations

|Risk|Mitigation|
|---|---|
|**Seven-Gate bottlenecks** at Policy Committee/Legal stages|Batch similar policies; pre-schedule committee slots; use LLM for initial compliance checks|
|**Policy Champion overload** with multiple documents|Limit 3 policies per champion; leverage AI for draft generation to reduce workload|
|**Version control complexity** with new workflow|Implement naming convention: PolicyName_v1.0_Gate3_YYYYMMDD; SharePoint check-in/out|
|**Training capacity** for Gate 7 requirements|Create LLM-generated training summaries; prioritize high-impact policy training|
|**Cross-functional coordination** delays|Establish Policy Committee standing meetings; use automated workflow notifications|

## 6. Data & Tool Requirements

**Required Infrastructure:**

- SharePoint libraries with Seven-Gate workflow states
- Enhanced Policy Tracker with fields: Gap Source, Current Gate, Committee Review Date, Board Required (Y/N)
- Gap register integrated with Policy Tracker
- Automated gate progression notifications

**Metadata Requirements:**

- Policy type, audience, risk level (determines if Gate 6 needed)
- SME assignments, review scores (human upvotes + LLM scores)
- Training completion tracking
- Version history with gate progression

**Missing Tools:**

- LLM integration for policy review and scoring
- Workflow automation for gate transitions
- Dashboard showing policies by gate status
- Training acknowledgment system

## 7. AI/SaaS Opportunity Lens

|Phase|Human-in-the-Loop|AI-in-the-Loop Value|
|---|---|---|
|**Gap Identification**|Confirms true gaps|Scans documents to identify missing coverage areas against compliance frameworks|
|**Draft Creation (Gate 2)**|Reviews/approves AI drafts|Generates initial policy text from templates and best practices|
|**SME Review**|Makes final decisions|Provides consistency scoring, flags ambiguous language, suggests improvements|
|**Committee Review (Gate 3)**|Strategic alignment check|Cross-references mission statements, identifies conflicts with existing policies|
|**Legal Review (Gate 4)**|Final compliance approval|Pre-screens for regulatory keywords, citation accuracy, legal language clarity|
|**Training Creation (Gate 7)**|Validates content|Auto-generates training materials, quizzes, and acknowledgment forms|

## 8. Clarifying Questions

1. **Gap Register Format**: Should the gap register be a separate SharePoint list or integrated into the Policy Tracker?
2. **LLM Model Selection**: Preference for specific LLM models/platforms for policy review scoring?
3. **Board Threshold**: What criteria determine if a policy requires Board ratification (Gate 6)?
4. **Upvote Mechanism**: How will human upvotes be collected—SharePoint ratings, separate survey, or integrated form?
5. **Document Versioning Standards**: Should we adopt a specific standard (e.g., ISO 9001, major.minor.patch)?
6. **Policy Committee Composition**: Are the five areas (HR, Finance, IT, Risk, Mission) fixed, or flexible by policy type?
7. **Training Acknowledgment**: Legal requirement for signed acknowledgments, or digital confirmation sufficient?
8. **AI Prompt Library**: Should we develop standardized prompts for each gate's AI assistance?