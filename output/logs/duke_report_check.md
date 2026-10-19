# Duke DPRC report (Berlind 2019), sections 1 and 5, against our files (aggregates only)

NC records. The report covers 2006-2018; our files start in 2007, so its numbers are compared with 2007-2018 (12 years instead of 13: fewer appearances are possible). Like the report, a household is a FAMILYID (all family records, subfamilies included); primary families are shown too. Report values marked 'read off its figure' are approximate.

Notes: FAMILYIDs listed more than once in a year: 0 records in all years (0.0%); one row each was kept, primary family first; ACS 1-year 2025: not available (HTTP 404: <!doctype html><html lang="en"><head><title>HTTP Status 404 ? Not Found</title><style type="text/css">body {font-family:Tahoma,Arial,sans-serif;} h1,).

## 1. Families and appearances

families: distinct FAMILYIDs. appearances: years in the NC files. no address: share of families with no usable address in any year (left out of the address statistics). addresses: distinct mailing addresses per FAMILYID (house number, street and ZIP, or PO box / rural route and ZIP), so a family never seen to move has 1. LOCATIONIDs: distinct Data Axle dwelling IDs (families with a LOCATIONID in every year). last column: of those families with 2+ addresses, the share whose LOCATIONID never changed (a hint that some 'moves' are re-spelled addresses).

```
                  universe   families mean appearances   SD no address mean addresses mean LOCATIONIDs 2+ addresses, 1 LOCATIONID
      report: NC 2006-2018 13,874,976             4.50 4.12                                                                      
     all records 2007-2018 13,435,521             4.41 3.86       3.2%           1.19             1.28                      49.8%
primary families 2007-2018 10,228,976             4.52 3.97       4.2%           1.18             1.00                     100.0%
     all records 2007-2025 19,731,447             5.31 5.48       2.3%           1.21             1.37                      41.5%
primary families 2007-2025 14,033,029             5.45 5.64       3.2%           1.20             1.00                     100.0%
```

### Distribution of appearances, all records 2007-2018

Report bars (2006-2018, approximate): 1: 32.0%, 2: 18.0%, 3: 9.5%, 4: 6.5%, 5: 4.8%, 6: 4.0%, 7: 3.3%, 8: 2.8%, 9: 2.6%, 10: 2.5%, 11: 2.2%, 12: 2.7%, 13: 10.5%. Among families with an address: moves = addresses - 1; moved = share with 2+ addresses.

```
 appearances  families  addresses  moves  addresses_with_unit  locationids moved share
           1 4,100,720       1.00   0.00                 1.00         1.00  0.0% 30.5%
           2 2,405,526       1.10   0.10                 1.11         1.26  9.6% 17.9%
           3 1,345,128       1.21   0.21                 1.23         1.41 18.5% 10.0%
           4   858,160       1.29   0.29                 1.32         1.52 23.8%  6.4%
           5   662,474       1.36   0.36                 1.39         1.58 27.3%  4.9%
           6   547,112       1.41   0.41                 1.44         1.62 29.5%  4.1%
           7   445,993       1.43   0.43                 1.46         1.62 30.1%  3.3%
           8   393,176       1.44   0.44                 1.46         1.61 30.5%  2.9%
           9   366,283       1.45   0.45                 1.47         1.59 30.6%  2.7%
          10   345,828       1.49   0.49                 1.51         1.55 33.4%  2.6%
          11   376,784       1.49   0.49                 1.50         1.47 33.5%  2.8%
          12 1,588,337       1.30   0.30                 1.31         1.20 22.9% 11.8%
```

### Primary families 2007-2018

```
 appearances  families  addresses  moves  addresses_with_unit  locationids moved share
           1 3,231,324       1.00   0.00                 1.00          1.0  0.0% 31.6%
           2 1,693,398       1.10   0.10                 1.12          1.0 10.3% 16.6%
           3   962,312       1.21   0.21                 1.23          1.0 18.5%  9.4%
           4   628,437       1.28   0.28                 1.32          1.0 23.6%  6.1%
           5   482,736       1.34   0.34                 1.37          1.0 26.4%  4.7%
           6   391,818       1.37   0.37                 1.40          1.0 27.7%  3.8%
           7   331,603       1.39   0.39                 1.42          1.0 28.7%  3.2%
           8   296,173       1.40   0.40                 1.43          1.0 29.3%  2.9%
           9   289,006       1.40   0.40                 1.42          1.0 29.3%  2.8%
          10   278,275       1.42   0.42                 1.45          1.0 31.0%  2.7%
          11   322,780       1.41   0.41                 1.43          1.0 30.9%  3.2%
          12 1,321,114       1.25   0.25                 1.25          1.0 19.9% 12.9%
```

## 1b. The report's regressions

All family records 2007-2018, one row per FAMILYID with complete data. Regressors are means over the family's years (log income in $1,000 of 2018, CPI-U; own/rent and marital codes 0-9 as numbers; CHILDRENHHCOUNT; LENGTH_OF_RESIDENCE), race from the first known Ethnicity_Code_1 grouped with config/ethnicity_groups.yaml (base: Asian; the report's race variable may come from its wru estimates and has Mixed, Native American and Pacific Islander groups we cannot form), and the head's first known age code (earliest year with a code A-M; base: under 25; J = 65+ inferred). Moves: unique addresses - 1, families seen 4+ times with an address. The report's scatter counts addresses, but its moves coefficients imply a mean outcome well below 1, so its regression must count moves. OLS, classical SEs. Last row: the mean outcome the report's coefficients would give at our regressor means; far from our mean, it points to different units or variable definitions.

```
                                                  regressor report: appearances ours: appearances (SE) report: moves ours: moves = addresses - 1 (SE)
                                                  Intercept               -1.31          0.239 (0.006)          0.31                    0.647 (0.003)
                                         Mean log HH income               0.523          0.306 (0.001)          0.11                    0.085 (0.001)
                                       Mean own/rent status                0.13          0.148 (0.000)         -0.07                   -0.067 (0.000)
                                              Mean children                1.47          1.217 (0.002)          0.02                    0.009 (0.001)
                                        Mean marital status                0.12          0.160 (0.000)          0.01                    0.016 (0.000)
                                   Mean length of residence                0.19          0.193 (0.000)         -0.01                   -0.013 (0.000)
                                                      Black                0.62          0.675 (0.006)          0.11                    0.062 (0.002)
                                                   Hispanic                0.15          0.078 (0.006)         -0.01                   -0.032 (0.003)
                                                      White                0.27          0.601 (0.005)          0.06                    0.056 (0.002)
                                                      Other               -0.08          0.319 (0.019)          0.04                    0.024 (0.007)
                                               Race missing                             -1.479 (0.005)                                 -0.027 (0.002)
                                                  Age 25-29                0.15         -0.053 (0.003)          0.19                   -0.005 (0.001)
                                                  Age 30-34                0.48          0.193 (0.003)          0.27                   -0.066 (0.001)
                                                  Age 35-39                0.84          0.346 (0.003)           0.3                   -0.099 (0.001)
                                                  Age 40-44                1.11          0.295 (0.003)          0.25                   -0.127 (0.001)
                                                  Age 45-49                1.58          0.302 (0.003)          0.19                   -0.132 (0.001)
                                                  Age 50-54                1.85          0.183 (0.003)          0.15                   -0.129 (0.001)
                                                  Age 55-59                2.26          0.137 (0.004)          0.14                   -0.111 (0.002)
                                                  Age 60-64                2.64          0.028 (0.004)          0.13                   -0.093 (0.002)
                                         Age 65+ (inferred)                2.84         -1.432 (0.006)          0.03                    0.013 (0.002)
                                                  Age 65-69                3.05          0.011 (0.005)          0.19                   -0.066 (0.002)
                                                  Age 70-74                3.23         -0.185 (0.006)          0.21                   -0.017 (0.002)
                                                    Age 75+                2.99         -0.898 (0.005)          0.28                    0.029 (0.002)
                                                         R2               0.524                  0.499         0.101                            0.097
                                                          N                                 13,435,521                                      5,458,736
                                                  mean of y                                       4.41                                           0.37
mean of y implied by the report's coefficients at our means                                       4.70                                           0.41
```

## 5. Age of the head of household

HEAD_HH_AGE_CODE by year: missing share; J (65+ inferred per the Data Axle dictionary) among known codes; shares of ACS age bands among known codes (65-74 = K+L, 75+ = M; the report's second grouping puts J with 75+); 65+ = J+K+L+M; and 65+ if J is treated as missing, a sensitivity check because an earlier project Q&A note treated J as missing. ACS: age of householder, B25007, 1-year.

```
 year records age missing J of known  <25 25-44 65-74 (K,L) 75+ (M) 75+ incl. J   65+ 65+ if J missing ACS <25 ACS 25-44 ACS 65-74 ACS 75+ ACS 65+
 2007     all        0.0%       2.0% 4.3% 41.6%        8.4%    5.7%        7.7% 16.2%            14.5%    5.4%     37.2%     10.5%    9.1%   19.5%
 2008     all        0.0%       1.9% 4.4% 40.6%        8.8%    6.1%        8.0% 16.8%            15.2%    5.1%     37.0%     10.7%    9.1%   19.8%
 2009     all        0.0%       1.2% 6.3% 39.9%        8.9%    7.2%        8.4% 17.2%            16.3%    5.7%     36.0%     11.2%    9.3%   20.4%
 2010     all        0.0%       3.9% 4.7% 34.3%        9.4%    7.7%       11.6% 21.0%            17.8%    4.5%     35.2%     12.0%    9.3%   21.3%
 2011     all        0.0%       3.9% 4.0% 34.6%        9.8%    7.9%       11.8% 21.6%            18.4%    4.3%     34.9%     12.0%    9.4%   21.5%
 2012     all        0.0%       3.7% 4.3% 34.1%       10.3%    8.2%       11.8% 22.1%            19.1%    4.3%     34.3%     13.0%    9.7%   22.8%
 2013     all        0.0%       3.6% 6.1% 34.0%       10.4%    7.8%       11.5% 21.9%            18.9%    4.4%     33.6%     13.4%    9.8%   23.2%
 2014     all        0.0%       3.4% 5.6% 33.0%       11.0%    8.3%       11.7% 22.7%            20.0%    4.2%     33.3%     14.1%    9.9%   24.0%
 2015     all        0.0%       3.6% 4.5% 31.8%       11.9%    8.7%       12.3% 24.2%            21.3%    4.2%     32.7%     14.4%   10.0%   24.5%
 2016     all        0.0%       1.6% 5.3% 31.9%       12.8%    9.1%       10.7% 23.6%            22.3%    3.9%     32.5%     14.8%   10.1%   24.9%
 2017     all        0.0%       1.6% 5.8% 32.5%       12.6%    9.1%       10.7% 23.3%            22.1%    3.8%     32.3%     15.2%   10.3%   25.5%
 2018     all        0.0%       1.6% 5.3% 34.3%       12.3%    9.1%       10.7% 23.0%            21.7%    3.9%     32.0%     15.3%   10.7%   26.1%
 2019     all        0.0%       1.5% 4.7% 33.6%       12.9%    9.6%       11.1% 24.0%            22.8%    3.8%     31.9%     15.7%   10.9%   26.7%
 2020     all        0.0%       2.4% 5.6% 33.6%       12.8%    9.6%       11.9% 24.8%            23.0%                                            
 2021     all        0.0%       2.2% 7.2% 34.7%       12.6%    9.1%       11.3% 23.9%            22.2%    4.2%     31.9%     16.1%   10.5%   26.7%
 2022     all        0.0%       2.3% 6.7% 34.1%       12.9%   10.0%       12.3% 25.2%            23.4%    4.5%     32.6%     16.1%   11.0%   27.1%
 2023     all        0.0%       2.1% 6.2% 33.0%       13.5%   11.2%       13.2% 26.8%            25.2%    4.3%     32.9%     16.1%   11.3%   27.4%
 2024     all        0.0%       1.8% 5.2% 33.1%       13.9%   12.0%       13.8% 27.7%            26.4%    4.6%     32.8%     16.1%   11.7%   27.8%
 2025     all        0.0%       1.4% 5.5% 37.4%       12.9%   10.9%       12.3% 25.2%            24.1%                                            
 2007 primary        0.0%       2.2% 3.6% 39.6%        9.3%    6.2%        8.4% 17.6%            15.8%    5.4%     37.2%     10.5%    9.1%   19.5%
 2008 primary        0.0%       2.1% 3.6% 38.5%        9.7%    6.6%        8.7% 18.4%            16.7%    5.1%     37.0%     10.7%    9.1%   19.8%
 2009 primary        0.0%       1.3% 4.3% 38.0%       10.0%    8.0%        9.4% 19.4%            18.3%    5.7%     36.0%     11.2%    9.3%   20.4%
 2010 primary        0.0%       4.1% 3.1% 32.6%       10.5%    8.5%       12.7% 23.1%            19.8%    4.5%     35.2%     12.0%    9.3%   21.3%
 2011 primary        0.0%       4.1% 2.8% 32.3%       10.9%    8.8%       12.9% 23.8%            20.5%    4.3%     34.9%     12.0%    9.4%   21.5%
 2012 primary        0.0%       3.8% 2.9% 31.7%       11.6%    9.2%       13.0% 24.6%            21.6%    4.3%     34.3%     13.0%    9.7%   22.8%
 2013 primary        0.0%       3.8% 3.9% 30.5%       12.3%    9.3%       13.1% 25.4%            22.5%    4.4%     33.6%     13.4%    9.8%   23.2%
 2014 primary        0.0%       3.6% 3.5% 29.7%       12.9%    9.8%       13.4% 26.3%            23.6%    4.2%     33.3%     14.1%    9.9%   24.0%
 2015 primary        0.0%       3.7% 3.1% 28.5%       13.7%   10.1%       13.8% 27.6%            24.8%    4.2%     32.7%     14.4%   10.0%   24.5%
 2016 primary        0.0%       1.8% 3.4% 28.4%       14.9%   10.8%       12.6% 27.5%            26.2%    3.9%     32.5%     14.8%   10.1%   24.9%
 2017 primary        0.0%       1.7% 3.8% 28.6%       14.9%   11.1%       12.8% 27.7%            26.4%    3.8%     32.3%     15.2%   10.3%   25.5%
 2018 primary        0.0%       1.8% 3.4% 29.4%       14.8%   11.3%       13.1% 27.9%            26.6%    3.9%     32.0%     15.3%   10.7%   26.1%
 2019 primary        0.0%       1.7% 3.0% 28.6%       15.5%   11.9%       13.5% 29.1%            27.9%    3.8%     31.9%     15.7%   10.9%   26.7%
 2020 primary        0.0%       2.3% 3.6% 28.5%       15.7%   12.1%       14.4% 30.1%            28.4%                                            
 2021 primary        0.0%       2.3% 4.4% 29.4%       15.5%   11.8%       14.1% 29.6%            27.9%    4.2%     31.9%     16.1%   10.5%   26.7%
 2022 primary        0.0%       2.4% 4.2% 29.1%       15.6%   12.5%       15.0% 30.5%            28.8%    4.5%     32.6%     16.1%   11.0%   27.1%
 2023 primary        0.0%       2.0% 4.1% 28.7%       15.9%   13.5%       15.5% 31.4%            30.1%    4.3%     32.9%     16.1%   11.3%   27.4%
 2024 primary        0.0%       1.7% 3.3% 28.6%       16.4%   14.6%       16.2% 32.7%            31.5%    4.6%     32.8%     16.1%   11.7%   27.8%
 2025 primary        0.0%       1.4% 3.4% 30.6%       16.0%   14.4%       15.8% 31.8%            30.9%                                            
```

### Report's 5-year windows: share of heads 65+

```
   window report infoUSA (figure) ours all ours primary ours all, J missing report ACS weighted (figure) ACS 1-year mean
2006-2010                   17.5%    17.8%        19.6%               15.9%                        20.5%           20.3%
2012-2016                   23.5%    22.9%        26.3%               20.4%                        24.0%           23.9%
```

Figures: `output/figures/duke_appearances.png`, `output/figures/duke_age.png`.
