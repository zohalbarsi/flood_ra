# Demographics: infoUSA vs Census (aggregates only)

Households = primary families (PRIMARY_FAMILY_IND = 1), study states. Census = ACS 1-year state estimates (no 2020 release). Figures: `output/figures/`; full tables: `output/tables/`. Census tables cached in `benchmarks/`.

Notes: ACS 1-year 2025: not available (HTTP 404: <!doctype html><html lang="en"><head><title>HTTP Status 404 ? Not Found</title><style type="text/css">body {font-family:Tahoma,Arial,sans-serif;} h1,)

## Owners and renters (primary families)

owner share duke (plotted): OWNER_RENTER_STATUS 7-9 among households coded 0-9, so the unknowns (4-6) count as renters, as in the Duke DPRC report's Table 6; it moves with Data Axle's recoding of unknowns (2015, 2019, 2025). owner share: 7-9 among households with 0-3 or 7-9; reported: 9 among 9 and 0; status unknown: share coded 4-6 or missing.

```
 year state households owner share duke owner share owner share reported status unknown ACS owner share ACS households
 2007    NC  3,775,263            64.5%       87.1%                99.6%          25.9%           68.3%      3,540,875
 2008    NC  3,637,047            65.8%       87.8%                99.7%          25.0%           68.2%      3,595,175
 2009    NC  3,785,298            65.6%       84.9%                99.8%          22.7%           67.2%      3,646,095
 2010    NC  3,771,336            66.7%       86.1%                99.8%          22.5%           67.2%      3,670,859
 2011    NC  3,729,062            64.8%       87.8%                99.8%          26.2%           66.5%      3,683,364
 2012    NC  3,763,390            65.2%       87.7%                99.9%          25.7%           65.4%      3,731,325
 2013    NC  4,000,670            63.6%       85.9%                99.8%          25.9%           64.3%      3,757,480
 2014    NC  3,937,660            65.4%       86.8%                99.9%          24.6%           64.2%      3,790,620
 2015    NC  3,808,026            71.8%       88.2%                99.9%          18.6%           63.9%      3,843,745
 2016    NC  3,886,947            72.9%       87.9%                99.9%          17.1%           64.2%      3,882,423
 2017    NC  4,026,312            71.6%       86.6%                99.9%          17.3%           65.4%      3,955,069
 2018    NC  4,140,738            71.8%       87.0%                99.9%          17.5%           65.1%      4,011,462
 2019    NC  4,168,617            71.9%       81.2%                88.9%          11.5%           65.3%      4,046,348
 2020    NC  4,308,142            71.1%       80.7%                89.8%          11.9%                               
 2021    NC  4,409,523            71.6%       81.1%                90.6%          11.7%           66.9%      4,179,632
 2022    NC  4,294,086            73.9%       83.2%                91.4%          11.2%           66.7%      4,299,266
 2023    NC  4,035,079            76.3%       85.3%                93.1%          10.6%           66.3%      4,392,669
 2024    NC  4,312,416            76.4%       85.1%                92.8%          10.3%           66.8%      4,496,359
 2025    NC  4,751,488            64.4%       82.7%                92.3%          22.1%                               
 2007    SC  1,736,485            66.2%       89.4%                99.6%          25.9%           70.0%      1,702,564
 2008    SC  1,687,212            67.9%       90.0%                99.7%          24.6%           70.6%      1,702,300
 2009    SC  1,648,722            68.5%       88.8%                99.8%          22.8%           70.1%      1,730,232
 2010    SC  1,663,413            69.5%       89.2%                99.9%          22.1%           68.7%      1,761,393
 2011    SC  1,710,088            66.4%       89.4%                99.9%          25.8%           69.2%      1,768,834
 2012    SC  1,723,167            67.2%       89.8%                99.9%          25.2%           68.1%      1,787,340
 2013    SC  1,824,279            66.4%       89.1%                99.9%          25.4%           68.2%      1,794,989
 2014    SC  1,764,586            68.9%       90.4%                99.9%          23.8%           68.0%      1,826,914
 2015    SC  1,780,444            74.2%       90.4%                99.9%          17.9%           68.1%      1,857,768
 2016    SC  1,845,788            76.6%       91.2%                99.9%          16.1%           68.6%      1,877,887
 2017    SC  1,892,238            76.1%       90.9%                99.9%          16.2%           68.7%      1,905,100
 2018    SC  1,951,397            75.6%       90.5%                99.9%          16.5%           69.3%      1,927,991
 2019    SC  1,999,947            75.3%       84.4%                90.2%          10.9%           70.3%      1,975,915
 2020    SC  2,033,779            75.1%       84.7%                91.1%          11.3%                               
 2021    SC  2,022,474            76.1%       85.6%                91.5%          11.1%           71.8%      2,049,972
 2022    SC  2,022,720            77.3%       86.6%                92.3%          10.7%           72.0%      2,136,080
 2023    SC  1,943,310            79.8%       88.5%                93.6%           9.8%           72.4%      2,177,733
 2024    SC  2,096,749            80.7%       88.8%                93.4%           9.1%           72.3%      2,222,890
 2025    SC  2,215,109            71.6%       88.8%                93.1%          19.4%                               
```

## Children

```
 year state children share ACS children share children per hh ACS children per hh
 2007    NC          10.0%              33.9%            0.13                0.62
 2008    NC          10.4%              33.7%            0.14                0.62
 2009    NC          11.0%              33.0%            0.15                0.62
 2010    NC          13.5%              32.9%            0.18                0.62
 2011    NC          12.8%              32.3%            0.17                0.62
 2012    NC          19.7%              32.3%            0.26                0.61
 2013    NC          18.2%              31.4%            0.24                0.61
 2014    NC          19.0%              31.4%            0.23                0.60
 2015    NC          19.4%              31.0%            0.23                0.60
 2016    NC          29.3%              31.0%            0.46                0.59
 2017    NC          31.1%              30.5%            0.50                0.58
 2018    NC          31.0%              30.1%            0.47                0.57
 2019    NC          33.6%              29.9%            0.55                0.57
 2020    NC          34.2%                               0.54                    
 2021    NC          32.3%              28.6%            0.51                0.55
 2022    NC          30.7%              29.0%            0.53                0.53
 2023    NC          29.3%              28.4%            0.54                0.53
 2024    NC          25.8%              28.6%            0.48                0.52
 2025    NC          22.9%                               0.41                    
 2007    SC          10.3%              33.0%            0.14                0.62
 2008    SC          10.6%              32.8%            0.15                0.63
 2009    SC          11.6%              32.3%            0.16                0.62
 2010    SC          13.8%              31.9%            0.19                0.61
 2011    SC          12.9%              32.2%            0.17                0.61
 2012    SC          20.3%              31.9%            0.27                0.60
 2013    SC          19.0%              30.9%            0.24                0.60
 2014    SC          20.4%              29.5%            0.25                0.59
 2015    SC          19.8%              29.6%            0.23                0.59
 2016    SC          29.0%              29.1%            0.45                0.59
 2017    SC          30.7%              29.2%            0.49                0.58
 2018    SC          30.5%              28.7%            0.46                0.57
 2019    SC          32.9%              28.4%            0.52                0.56
 2020    SC          33.2%                               0.51                    
 2021    SC          32.3%              28.3%            0.50                0.54
 2022    SC          28.9%              28.0%            0.50                0.52
 2023    SC          27.0%              28.4%            0.49                0.52
 2024    SC          23.6%              27.8%            0.43                0.52
 2025    SC          21.8%                               0.38                    
```

## Income, wealth and home value (nominal dollars)

infoUSA income is top-coded at $500,000 (share top-coded shown); wealth has no Census benchmark.

```
 year state median income ACS median income topcoded median wealth mean wealth median home value ACS median home value
 2007    NC        46,000            44,670     0.1%     2,745,000   2,871,977           125,000               145,700
 2008    NC        48,000            46,549     0.2%     2,793,000   2,937,920           140,000               154,500
 2009    NC        54,000            43,674     0.7%     2,858,000   3,016,787           158,000               155,500
 2010    NC        51,000            43,326     0.6%     1,833,000   1,876,803           135,000               154,200
 2011    NC        51,000            43,916     0.6%     1,841,000   1,886,051           136,000               153,700
 2012    NC        53,000            45,150     0.6%     1,874,000   1,916,526           155,000               150,100
 2013    NC        51,000            45,906     0.6%     1,843,000   1,894,951           155,000               154,300
 2014    NC        39,000            46,556     0.1%     1,242,000   1,398,022           156,000               155,000
 2015    NC        42,000            47,830     0.1%     1,296,000   1,450,516           157,000               160,100
 2016    NC        45,000            50,584     0.3%     1,305,000   1,458,468           151,000               165,400
 2017    NC        45,000            52,752     0.3%     1,289,000   1,444,867           152,000               171,200
 2018    NC        46,000            53,855     0.3%     1,357,000   1,469,250           162,000               180,600
 2019    NC        47,000            57,341     0.3%     1,390,000   1,504,196           169,000               193,200
 2020    NC        48,000                       0.4%     1,395,000   1,508,159           175,000                      
 2021    NC        50,000            61,972     0.4%     1,425,000   1,524,009           178,000               236,900
 2022    NC        53,000            67,481     0.4%     1,474,000   1,563,915           187,000               280,600
 2023    NC        56,000            70,804     0.5%     1,539,000   1,617,318           195,000               308,600
 2024    NC        59,000            73,958     0.6%     1,577,000   1,666,886           220,000               333,000
 2025    NC        53,000                       0.0%     5,185,000   5,082,669           245,000                      
 2007    SC        43,000            43,329     0.3%     2,669,000   2,831,369           123,000               133,900
 2008    SC        45,000            44,625     0.5%     2,713,000   2,885,459           128,000               138,700
 2009    SC        50,000            42,442     0.4%     2,781,000   2,956,912           146,000               137,500
 2010    SC        47,000            42,018     0.4%     1,772,000   1,828,992           121,000               138,100
 2011    SC        46,000            42,367     0.4%     1,769,000   1,829,322           122,000               136,000
 2012    SC        49,000            43,107     0.4%     1,800,000   1,863,009           139,000               135,500
 2013    SC        49,000            44,163     0.5%     1,789,000   1,861,928           140,000               139,200
 2014    SC        40,000            45,238     0.1%     1,230,000   1,375,568           144,000               140,000
 2015    SC        41,000            47,238     0.1%     1,270,000   1,411,166           143,000               148,600
 2016    SC        43,000            49,501     0.1%     1,276,000   1,421,989           134,000               153,900
 2017    SC        44,000            50,570     0.1%     1,254,000   1,405,656           136,000               161,800
 2018    SC        45,000            52,306     0.1%     1,340,000   1,452,487           145,000               170,800
 2019    SC        46,000            56,227     0.1%     1,371,000   1,483,972           153,000               179,800
 2020    SC        46,000                       0.1%     1,386,000   1,489,969           157,000                      
 2021    SC        50,000            59,318     0.1%     1,441,000   1,532,783           165,000               213,500
 2022    SC        52,000            64,115     0.1%     1,471,000   1,554,099           173,000               254,600
 2023    SC        57,000            67,804     0.2%     1,551,000   1,641,739           189,000               272,900
 2024    SC        59,000            72,350     0.2%     1,571,000   1,653,680           191,000               299,500
 2025    SC        52,000                       0.0%     5,240,000   5,147,050           210,000                      
```

## Race and ethnicity of the first person / householder

Shares of households with a known ethnicity code; ethnicity missing: share with code 00 or blank. Census: race and Hispanic origin of the householder (white = non-Hispanic).

```
 year state ethnicity missing white share ACS white share black share ACS black share hispanic share ACS hispanic share asian share ACS asian share
 2007    NC             39.1%       87.0%           71.1%        8.2%           20.8%           2.9%               4.8%        1.7%            1.5%
 2008    NC             34.7%       86.9%           71.1%        8.2%           20.8%           3.0%               4.9%        1.7%            1.4%
 2009    NC             31.3%       86.5%           70.8%        8.6%           20.9%           3.0%               4.8%        1.7%            1.5%
 2010    NC             25.8%       86.3%           69.9%        8.6%           21.0%           3.1%               5.4%        1.8%            1.7%
 2011    NC             21.2%       86.3%           69.9%        8.4%           21.1%           3.2%               5.5%        1.9%            1.7%
 2012    NC             13.7%       85.8%           69.6%        8.7%           20.9%           3.4%               5.6%        1.9%            1.9%
 2013    NC              4.2%       84.8%           69.5%        9.2%           20.9%           3.8%               5.7%        2.1%            1.9%
 2014    NC              4.1%       84.6%           68.6%        9.3%           21.3%           3.8%               6.0%        2.1%            2.0%
 2015    NC              4.2%       84.8%           68.5%        8.9%           21.2%           3.9%               6.2%        2.2%            2.1%
 2016    NC              4.2%       84.5%           68.7%        9.0%           20.9%           4.1%               6.1%        2.2%            2.1%
 2017    NC              4.3%       84.1%           68.0%        9.0%           21.1%           4.3%               6.3%        2.4%            2.3%
 2018    NC              3.6%       82.9%           67.4%        9.8%           21.3%           4.6%               6.5%        2.5%            2.5%
 2019    NC              3.7%       82.9%           67.2%        9.7%           21.4%           4.7%               6.5%        2.5%            2.4%
 2020    NC              3.7%       82.6%                        9.6%                           5.0%                           2.7%                
 2021    NC              3.7%       82.0%           65.5%        9.7%           20.6%           5.3%               6.7%        2.8%            2.5%
 2022    NC              3.8%       81.8%           65.2%        9.5%           20.8%           5.6%               7.1%        2.9%            2.6%
 2023    NC              3.9%       81.8%           64.6%        9.4%           20.6%           5.7%               7.8%        3.0%            2.9%
 2024    NC              3.8%       81.3%           63.8%        9.5%           20.4%           5.9%               8.4%        3.1%            3.1%
 2025    NC              3.9%       80.3%                        9.9%                           6.4%                           3.2%                
 2007    SC             39.3%       85.8%           68.6%       11.3%           26.8%           1.8%               2.6%        1.1%            1.1%
 2008    SC             35.2%       85.9%           69.1%       11.0%           26.4%           1.9%               2.6%        1.1%            0.9%
 2009    SC             30.1%       85.8%           68.6%       11.1%           26.6%           1.9%               2.8%        1.1%            1.1%
 2010    SC             24.6%       85.6%           68.6%       11.2%           26.0%           2.0%               3.1%        1.1%            1.1%
 2011    SC             20.4%       85.4%           68.1%       11.2%           26.3%           2.0%               3.4%        1.2%            1.1%
 2012    SC             13.2%       85.2%           68.2%       11.3%           26.0%           2.1%               3.5%        1.2%            1.0%
 2013    SC              4.1%       84.7%           67.8%       11.6%           26.4%           2.3%               3.6%        1.3%            1.1%
 2014    SC              4.1%       84.8%           68.3%       11.4%           25.7%           2.3%               3.6%        1.3%            1.2%
 2015    SC              4.2%       84.7%           67.7%       11.3%           26.3%           2.5%               3.8%        1.4%            1.1%
 2016    SC              4.2%       84.4%           67.8%       11.5%           26.0%           2.6%               3.7%        1.4%            1.3%
 2017    SC              4.2%       84.3%           67.7%       11.5%           25.7%           2.7%               4.0%        1.4%            1.3%
 2018    SC              3.5%       83.4%           67.7%       12.0%           25.7%           2.9%               4.0%        1.5%            1.2%
 2019    SC              3.5%       83.4%           67.4%       12.0%           25.8%           3.0%               3.9%        1.5%            1.4%
 2020    SC              3.6%       83.2%                       11.8%                           3.2%                           1.6%                
 2021    SC              3.6%       83.0%           66.3%       11.8%           24.6%           3.4%               4.3%        1.6%            1.3%
 2022    SC              3.7%       83.0%           66.1%       11.6%           24.4%           3.6%               4.7%        1.7%            1.5%
 2023    SC              3.7%       83.1%           65.9%       11.4%           24.2%           3.7%               5.2%        1.7%            1.6%
 2024    SC              3.6%       82.9%           65.2%       11.4%           23.7%           3.8%               5.6%        1.7%            1.7%
 2025    SC              3.7%       82.2%                       11.6%                           4.2%                           1.8%                
```

### Ethnicity codes and their groups

Most common Ethnicity_Code_1 values (all years; codes longer than 4 characters shown as patterns). group: from `config/ethnicity_groups.yaml` if it exists, else inferred: r_* is the correlation, across counties in 2017, of the code's share of households with the ACS share of each householder group; a code goes to the best group if r >= 0.4 and at least 0.15 above the next group. **Check the inferred groups against the Data Axle Ethnicity-Cultural Coding Datacard.**

```
     code share    group                source
       E5 40.1%    white ethnicity_groups.yaml
(missing) 10.8%  missing ethnicity_groups.yaml
       S3  9.1%    white ethnicity_groups.yaml
       IE  5.8%    white ethnicity_groups.yaml
       DE  4.8%    white ethnicity_groups.yaml
       W4  4.4%    white ethnicity_groups.yaml
       H5  3.5% hispanic ethnicity_groups.yaml
       LR  2.8%    black ethnicity_groups.yaml
       B5  2.7%    black ethnicity_groups.yaml
       FR  2.2%    white ethnicity_groups.yaml
       IT  1.9%    white ethnicity_groups.yaml
       J4  1.7%    white ethnicity_groups.yaml
       Q6  1.6%    black ethnicity_groups.yaml
       NL  1.4%    white ethnicity_groups.yaml
       Q9  0.8%    black ethnicity_groups.yaml
       SE  0.6%    white ethnicity_groups.yaml
       PL  0.5%    white ethnicity_groups.yaml
       IN  0.5%    asian ethnicity_groups.yaml
       Q7  0.5%    black ethnicity_groups.yaml
       CN  0.4%    asian ethnicity_groups.yaml
       A7  0.3%    asian ethnicity_groups.yaml
       Q8  0.3%    black ethnicity_groups.yaml
       DK  0.3%    white ethnicity_groups.yaml
       HU  0.2%    white ethnicity_groups.yaml
       RU  0.2%    white ethnicity_groups.yaml
       VN  0.2%    asian ethnicity_groups.yaml
       AT  0.2%    white ethnicity_groups.yaml
       NO  0.2%    white ethnicity_groups.yaml
       PT  0.2%    white ethnicity_groups.yaml
       GR  0.2%    white ethnicity_groups.yaml
       CZ  0.2%    white ethnicity_groups.yaml
       K5  0.1%    asian ethnicity_groups.yaml
       PH  0.1%    asian ethnicity_groups.yaml
       N3  0.1%    other ethnicity_groups.yaml
       JP  0.1%    asian ethnicity_groups.yaml
       SK  0.1%    white ethnicity_groups.yaml
       UA  0.1%    white ethnicity_groups.yaml
       FI  0.0%    white ethnicity_groups.yaml
       P4  0.0%    other ethnicity_groups.yaml
       RO  0.0%    white ethnicity_groups.yaml
```

## Tracts, 2017 (infoUSA) vs ACS 2015-2019

Tracts with at least 30 infoUSA households. r: correlation across tracts; means are unweighted tract means.

```
                         measure tracts    r infoUSA mean ACS mean
owner share, unknowns as renters  3,245 0.88        72.4%    65.7%
   owner share, known codes only  3,245 0.85        86.3%    65.7%
      Black share of Black+White  3,245 0.76        12.3%    26.7%
```
