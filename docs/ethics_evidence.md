# Ethics evidence for the use of public data

Project: forecasting weekly A&E attendance in Glasgow from weather, with a human-approved early-warning tool (MHW225671).
Prepared 16 November 2026. All links were opened on that date. Adapt the wording to the ethics form; do not paste it unread.

## Summary

The project uses only published, open data. It collects nothing from people: no participants, no surveys, no interviews,
no patient records. Two things need evidence: that the terms of each dataset allow this use, and that the health data
cannot identify anyone.

## 1. A&E attendance data (Public Health Scotland)

**What is used.** The "Weekly A&E Activity and Waiting Times" open dataset. The project takes one number per hospital
per week: the total attendances, for three hospitals (QEUH, GRI, RHC), from February 2015 to October 2026. It does not
use any breakdown by age, sex, deprivation, diagnosis or any other personal characteristic.

- Dataset page: https://www.opendata.nhs.scot/dataset/weekly-accident-and-emergency-activity-and-waiting-times

**Terms allow the use.** The dataset page states the licence as the UK Open Government Licence. Version 3.0 of that
licence grants a "worldwide, royalty-free, perpetual, non-exclusive licence" to copy, publish, adapt and use the
information, commercially or non-commercially.

- Licence text: https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/

The licence sets two conditions, and the project meets them as follows:

| Condition | How it is met |
|---|---|
| Acknowledge the source and link to the licence | The tool's pages and the README name Public Health Scotland and the licence and carry the statement below. The final report must too: "Contains public sector information licensed under the Open Government Licence v3.0." |
| Do not suggest official status or endorsement | The tool's pages and the README state that it is decision support only, not clinically validated, and not endorsed by Public Health Scotland or the NHS. |

**The data is aggregated and cannot identify individuals.**

- Each value is a weekly total for a whole hospital. Across the three hospitals and all 609 weeks used, the smallest
  weekly total is 209 attendances and the largest is 2,252. There are no small counts.
- Public Health Scotland publishes the data under its Statistical Disclosure Control protocol, which exists to "reduce
  the risk of personal identifiable information about data subjects" before release. The dataset page states that this
  protocol is followed.
  - Protocol: https://publichealthscotland.scot/publications/public-health-scotland-statistical-disclosure-protocol/public-health-scotland-statistical-disclosure-protocol-version-22/
- The dataset page describes the figures as accredited official statistics, reviewed by the Office for Statistics
  Regulation in October 2023.
- The Open Government Licence does not cover personal data. The publisher releasing the data under that licence is
  consistent with it containing none.
- The project does not link the data to any other dataset about people, so it adds no route to re-identification.

## 2. Weather and air-quality data (Open-Meteo)

**What is used.** Daily temperature, humidity, rainfall and particulate levels for Glasgow, from the Open-Meteo
historical, air-quality, forecast and previous-runs services. This is modelled environmental data for a location. It
contains no information about people.

**Terms allow the use.**

- Data licence: Creative Commons Attribution 4.0 (CC BY 4.0), which permits sharing and adapting with credit.
  https://open-meteo.com/en/licence
- Terms of use: the free service is for non-commercial use. The terms list "public research conducted at public
  institutions" and "use in educational content" as qualifying. https://open-meteo.com/en/terms

| Condition | How it is met |
|---|---|
| Non-commercial use only | A university honours project. No fees, advertising or commercial use. |
| Give credit and link to the licence | Credited in the report and README, with the Zenodo citation (Zippenfenig, 2023, doi:10.5281/ZENODO.7970649). |
| Stay within the request limits (10,000 calls a day) | The whole project makes a few dozen calls. |

## 3. Other ethical points

- **No human participants.** Nobody is recruited, observed or surveyed. The tool has not been tested with hospital staff.
- **Storage.** Only the open data is stored, on the student's computer. The tool's officer accounts are test accounts
  created by the student.
- **Risk of harm.** The tool is a prototype. It gives a forecast and a risk level, and a named person must approve any
  alert. It is labelled as decision support, not clinically validated, and it is not deployed in any hospital.
- **Honest reporting.** The report states the limits of the results, including that alerts catch only about a third to
  a half of high-pressure weeks.

## To check before submitting

1. Done on 17 November 2026: the tool's sign-in page and dashboard, and the README, now carry both credits, the exact Open
   Government Licence sentence and "not endorsed by Public Health Scotland or the NHS". The final report must carry them too.
2. Open the Open Government Licence and the Public Health Scotland disclosure protocol yourself before citing them.
3. If the project later uses any other dataset, or tests the tool with real staff, the application must be updated.
