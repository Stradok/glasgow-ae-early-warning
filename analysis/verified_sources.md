# Verified sources for the literature review

Checked on 2 Nov 2026 by opening each paper's publisher/PMC/IZA page (metadata + abstract).
Full texts were NOT read. Cite only what the abstract supports.

## A. Opened and verified

1. Ogata, S., Takegami, M., Ozaki, T., Nakashima, T., Onozuka, D., Murata, S., Nakaoku, Y., Suzuki, K., Hagihara, A., Noguchi, T., Iihara, K., Kitazume, K., Morioka, T., Yamazaki, S., Yoshida, T., Yamagata, Y. and Nishimura, K. (2021) 'Heatstroke predictions by machine learning, weather information, and an all-population registry for 12-hour heatstroke alerts', *Nature Communications*, 12, 4575. doi:10.1038/s41467-021-24823-0
   - 16 Japanese cities (~10 million people), per city per 12 hours.
   - Compared GLM, GAM, Random Forest, XGBoost. Best: hybrid GAM + under-sampled XGBoost.
   - MAPE on spikes: 14.8% (all heatstroke cases), 10.6% (admissions and deaths). Single-predictor GLM (WBGT): 43.0% and 37.7%.
   - Limits (as extracted): 16 Japanese cities; depends on weather-data accuracy; heatstroke definitions vary internationally.

2. Toure, M. et al. (2025) 'Machine Learning-Based Prediction of Heatwave-Related Hospitalizations: A Case Study in Matam, Senegal', *International Journal of Environmental Research and Public Health*, 22(9), 1349. doi:10.3390/ijerph22091349
   - One regional hospital (Ourossogui), 2017-2022, daily Tmax and heat index.
   - Compared Random Forest, XGBoost, GAM (1000-iteration bootstrap). RF best, R2 0.51-0.72.
   - Admissions peaked 3-5 days after heatwaves (delayed effect).
   - 14 authors (dc.creator list on the MDPI page).

3. Javari, P. and Javari, M. (2026) 'Heat stress and cardiovascular hospitalizations in a semi-arid megacity: a multi-method epidemiological and machine-learning analysis in Isfahan, Iran', *BMC Public Health*, 26, 1719. doi:10.1186/s12889-026-26909-0
   - CVD admissions 2019-2024; ERA5-Land reanalysis + six stations.
   - Quasi-Poisson, logistic regression, XGBoost, Random Forest. XGBoost AUC 0.84 (95% CI 0.81-0.87); heat index, WBGT and age most influential.
   - Not checked: exactly which outcome the AUC refers to.

4. Klauber, H. and Koch, N. (2023) 'Determinants of Heat Risk in an Aging Population: A Machine Learning Approach', *IZA Discussion Paper* No. 15996.
   - German population aged 65+, administrative insurance claims, ML regression.
   - Vulnerable: elderly with chronic disease, rural areas with higher poverty and less nursing care.
   - A working paper, not a peer-reviewed journal article.

5. Corcuera Hotz, I. and Hajat, S. (2020) 'The Effects of Temperature on Accident and Emergency Department Attendances in London: A Time-Series Regression Analysis', *International Journal of Environmental Research and Public Health*, 17(6), 1957. doi:10.3390/ijerph17061957
   - Daily A&E attendances, London, Apr 2007-Mar 2012; seasonally adjusted Poisson regression.
   - +1.0% overall (95% CI 0.8-1.4) per 1 C; highest risk in children and the most deprived areas.
   - Limits (as extracted): one air-pollution monitoring site; no data on adaptation such as air conditioning.
   - Closest UK A&E study found so far.

6. Weismann, D., Moeckel, M., Paeth, H. and Slagman, A. (2023) 'Modelling variations of emergency attendances using data on community mobility, climate and air pollution', *Scientific Reports*, 13, 20595. doi:10.1038/s41598-023-47857-4
   - Weekly aggregated data from 33 German hospitals, 2020 lockdown period; stepwise linear regression.
   - Mobility explained 63% of variation; lower air pollution another 6%.
   - Supports treating 2020 as a distortion period. (Author name: "Möckel" on the page.)

## B. Search result only (title/journal seen, page NOT opened)

- Tiggeloven, T. et al. (2025) 'The role of artificial intelligence for early warning systems', *iScience*. PubMed 41280665. The page scrape failed. The proposal's claim ("call for causal, transparent, inclusive AI with human accountability") is NOT verified.
- Reichstein et al. (2025), *Nature Communications*: NOT verified. A paper titled "Early warning of complex climate risk with integrated artificial intelligence" appeared in search, but its authors and journal were not confirmed.

## C. Seen only inside other papers' reference lists (exist; not opened)

- Marcilio, I., Hajat, S. and Gouveia, N. (2013) 'Forecasting daily emergency department visits using calendar variables and ambient temperature readings', *Academic Emergency Medicine*, 20(8), pp. 769-777. doi:10.1111/acem.12182
- Au-Yeung, S.W.M. et al. (2009) 'Predicting patient arrivals to an accident and emergency department', *Emergency Medicine Journal*, 26, pp. 241-244. doi:10.1136/emj.2007.051656
- Murtas, R. et al. (2022) 'Time-series cohort study to forecast emergency department visits in the city of Milan and predict high demand: a 2-day warning system', *BMJ Open*, 12(4), e056017. doi:10.1136/bmjopen-2021-056017
- Kovats, R.S., Hajat, S. and Wilkinson, P. (2004) 'Contrasting patterns of mortality and hospital admissions during hot weather and heat waves in Greater London, UK', *Occupational and Environmental Medicine*, 61, pp. 893-898. doi:10.1136/oem.2003.012047
- Method references: Breiman (2001) Random Forests, *Machine Learning* 45, 5-32; Chen and Guestrin (2016) XGBoost, KDD, 785-794; Hastie and Tibshirani (1986) Generalized Additive Models, *Statistical Science* 1, 297-310.

## D. Corrections needed to the Gyraq proposal text

1. Ogata et al.: the proposal says "using only weather and demographic data". Wrong. The target was an all-population heatstroke patient registry, plus weather.
2. Javari and Javari: the proposal says 2025. It is 2026.
3. Toure et al.: the proposal says RF, XGBoost and GAM "with a traditional statistical model". The paper compares those three; the GAM is the statistical one.
4. Klauber and Koch: add that it is German over-65s and a discussion paper.
5. "Most studies are single-site and report overall accuracy only": NOT supported. Ogata covers 16 cities. Do not claim this gap. A safer gap is "no Glasgow/Scotland weekly A&E forecasting study found so far", which still needs one more targeted search before it is written.

## E. Still to find (needed for a strong 50-mark review)

- PM2.5 / air quality and emergency attendances (UK or Scotland).
- ED demand forecasting baselines (seasonal naive, persistence, ARIMA).
- Scottish heat definition (the 2025 systematic review excerpt mentioned >=25 C for 3 days; Robertson et al. 2022 not opened).
- ERA5 reference (Hersbach et al. 2020) and Open-Meteo / PHS data documentation.
- Human-in-the-loop / responsible AI for early warning (open Tiggeloven properly).

## F. Candidates found in the 2 Nov novelty search (search excerpts only; OPEN EACH BEFORE CITING)

Verified from metadata text:
- Hersbach, H. et al. (2020) 'The ERA5 global reanalysis', *Quarterly Journal of the Royal Meteorological Society*, 146, pp. 1999-2049. doi:10.1002/qj.3803

Forecasting evaluation (supports the "persistence is hard to beat" point):
- arXiv 2603.20315 (Mar 2026, preprint) 'Rolling-Origin Validation Reverses Model Rankings in Multi-Step PM10 Forecasting: XGBoost, SARIMA, and Persistence'. XGBoost not consistently better than persistence under rolling-origin evaluation. Preprint: say so.
- Cerqueira, Torgo and Mozetic (2020) *Machine Learning* 109(11), 1997-2028; Tashman (2000) *Int. J. Forecasting* 16(4), 437-450; Hyndman and Athanasopoulos (2021) *Forecasting: Principles and Practice*, 3rd ed. (all listed in the arXiv reference list; not opened).

ED demand forecasting:
- 2025 systematic review 'Predictive modeling of hospital emergency department demand using artificial intelligence' (ScienceDirect pii S1386505625004320). XGBoost most widely used; many studies single-hospital.
- Sudarshan et al. (2021) *Computers in Biology and Medicine* 135, 104541 (meteorological + calendar information).
- Jilani et al. (2019) *Int. J. Medical Informatics* 129, 167-174.
- PMC11653554 (XGBoost best on two horizons); PMC2640341 (daily ED forecasting); a UK/London A&E study using weather forecasts (sethrf.com/files/AE_attendances.pdf, authors/journal to confirm).

Scotland and UK:
- PMC9594922 'Temperature-related mortality and associated vulnerabilities': Scotland, risk at both low and high temperatures (probably Robertson et al. 2022; confirm).
- Public Health Scotland 'Adverse weather and health' pages and heat-associated deaths report 2005-2024.
- ScienceDirect pii S0269749123011259: NO2, PM2.5, PM10 and health service attendance (country not confirmed).
- Met Office / UKHSA Heat-Health Alert service, impact-based since summer 2023 (Met Office page seen); ScienceDirect pii S1462901125002059 on the transition to impact-based alerting.
- 2025 systematic review of extreme temperatures and ED visits (ScienceDirect pii S0048969725005042).

Novelty check result: the first search surfaced NO study forecasting weekly A&E attendance from weather for Glasgow or Scotland. This is not proof that none exists.
