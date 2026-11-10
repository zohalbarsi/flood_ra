# The 2017 NC/SC households, followed to 2024 (counts and shares only)

Cohort: the 5,915,263 households that are a primary family in NC or SC in 2017 (household panel, step 08). The group is fixed: shares are of the whole cohort unless stated. Found: a record anywhere in the US files that year (same FAMILYID, or one the household continues under). Missing, back later: not found that year but found in a later one. Gone for good: not found that year or any later year up to 2024 (so in 2024 every household not found counts as gone). A household whose adults join another household, or split up, is not found from then on (step 08's links).

Figure: `output/figures/cohort_2017.png`. Tables with all counts: `output/tables/cohort_2017_by_year.csv`, `cohort_2017_attrition.csv`.

## The 2017 households

Median 2017 income $45,000; income quartile cut-offs $22,000, $45,000, $80,000.

```
     group         value households % of cohort
     state            NC  4,024,093       68.0%
     state            SC  1,891,170       32.0%
    tenure         owner  4,321,963       73.1%
    tenure        renter    590,555       10.0%
    tenure       unknown  1,002,745       17.0%
      race         asian     90,982        1.5%
      race         black    555,551        9.4%
      race      hispanic    213,942        3.6%
      race         other     37,909        0.6%
      race       unknown    251,382        4.2%
      race         white  4,765,497       80.6%
    income    1 (lowest)  1,500,214       25.4%
    income             2  1,501,026       25.4%
    income             3  1,449,764       24.5%
    income   4 (highest)  1,464,259       24.8%
  children   no children  4,084,610       69.0%
  children with children  1,830,653       30.9%
head's age      under 35    929,257       15.7%
head's age         35-44    919,686       15.6%
head's age         45-54  1,154,718       19.5%
head's age         55-64  1,208,664       20.4%
head's age   65 and over  1,702,938       28.8%
```

## Counts and attrition

```
 year     found  in NC/SC other states missing, back later gone for good found under a new FAMILYID
 2017 5,915,263 5,915,263            0                   0             0                     39,184
 2018 5,215,134 5,163,381       51,753             251,972       448,157                     50,247
 2019 4,903,230 4,826,966       76,264             290,452       721,581                     54,076
 2020 4,680,272 4,586,905       93,367             257,801       977,190                     58,246
 2021 4,411,353 4,305,191      106,162             256,609     1,247,301                     62,684
 2022 4,169,576 4,054,511      115,065             266,262     1,479,425                     65,464
 2023 3,813,534 3,696,858      116,676             358,407     1,743,322                     63,724
 2024 3,908,787 3,783,736      125,051                   0     2,006,476                     66,587
```

Shares of the 5,915,263 households; moved since last year: among households found that year and the year before, the share at a new address.

```
 year  found in NC/SC other states missing, back later gone for good moved since last year
 2017 100.0%   100.0%         0.0%                0.0%          0.0%                  4.9%
 2018  88.2%    87.3%         0.9%                4.3%          7.6%                  6.8%
 2019  82.9%    81.6%         1.3%                4.9%         12.2%                  4.5%
 2020  79.1%    77.5%         1.6%                4.4%         16.5%                  4.6%
 2021  74.6%    72.8%         1.8%                4.3%         21.1%                  4.6%
 2022  70.5%    68.5%         1.9%                4.5%         25.0%                  4.0%
 2023  64.5%    62.5%         2.0%                6.1%         29.5%                  3.4%
 2024  66.1%    64.0%         2.1%                0.0%         33.9%                  2.5%
```

## Demographics of the households found each year

Owner, renter, tenure unknown: OWNER_RENTER_STATUS 7-9, 0-3 and the rest, of households found; with children: among households with a known CHILDREN_IND; race of the first person (ethnicity.py) among households with a known code; head 65+: among households with a known HEAD_HH_AGE_CODE. These change with who stays in the files (attrition is not random, see below) and with Data Axle's recoding (tenure in 2019).

```
 year owner renter tenure unknown with children median income White Black Hispanic Asian head 65+
 2017 73.1%  10.0%          17.0%         30.9%        45,000 84.1%  9.8%     3.8%  1.6%    28.8%
 2018 78.0%   7.5%          14.5%         35.5%        49,000 84.1% 10.3%     3.5%  1.5%    32.6%
 2019 79.6%  11.8%           8.6%         40.6%        52,000 84.4% 10.2%     3.3%  1.4%    35.2%
 2020 81.8%  10.3%           8.0%         43.5%        54,000 84.6% 10.0%     3.3%  1.4%    37.7%
 2021 83.6%   9.3%           7.1%         43.8%        58,000 84.6%  9.9%     3.4%  1.5%    38.9%
 2022 84.9%   8.6%           6.6%         41.3%        60,000 84.7%  9.8%     3.3%  1.5%    40.9%
 2023 87.1%   7.1%           5.7%         39.2%        64,000 85.0%  9.7%     3.3%  1.5%    43.2%
 2024 87.9%   6.8%           5.3%         36.1%        66,000 84.7%  9.8%     3.3%  1.5%    45.4%
```

## Attrition by 2017 characteristics

Share of each 2017 group found in each year; last column: never found again after 2017.

```
     group         value  2018  2019  2020  2021  2022  2023  2024 never found after 2017
     state            NC 88.2% 82.4% 79.0% 74.9% 70.8% 64.1% 65.3%                   7.8%
     state            SC 88.0% 84.0% 79.5% 73.8% 69.9% 65.3% 67.7%                   7.0%
    tenure         owner 92.3% 88.6% 86.2% 81.7% 78.2% 73.2% 75.1%                   4.4%
    tenure        renter 74.3% 60.6% 52.6% 48.8% 43.2% 35.9% 35.2%                  19.3%
    tenure       unknown 78.4% 71.6% 64.4% 59.0% 53.3% 43.6% 45.4%                  14.3%
      race         asian 82.6% 74.5% 72.3% 69.7% 66.2% 59.6% 63.4%                  10.7%
      race         black 86.7% 81.0% 76.2% 71.4% 66.7% 60.3% 62.4%                   8.4%
      race      hispanic 80.6% 72.1% 68.3% 65.4% 61.4% 55.1% 57.2%                  11.9%
      race         other 84.8% 77.4% 74.4% 71.1% 67.1% 60.7% 63.1%                   9.9%
      race       unknown 87.1% 81.4% 77.8% 73.5% 69.5% 63.4% 64.5%                   8.6%
      race         white 88.9% 83.9% 80.2% 75.5% 71.5% 65.6% 67.1%                   7.2%
    income    1 (lowest) 80.8% 72.8% 67.1% 61.3% 55.8% 48.2% 50.4%                  12.6%
    income             2 86.4% 80.4% 76.1% 71.0% 66.4% 59.2% 61.9%                   8.6%
    income             3 90.9% 86.6% 83.6% 79.4% 75.7% 70.0% 71.8%                   5.6%
    income   4 (highest) 94.8% 92.1% 90.1% 87.1% 84.6% 81.1% 80.7%                   3.3%
  children   no children 84.6% 77.7% 73.4% 68.3% 63.8% 56.8% 58.9%                  10.0%
  children with children 96.2% 94.6% 92.0% 88.6% 85.3% 81.7% 82.1%                   2.2%
head's age      under 35 76.5% 66.3% 61.7% 58.5% 53.7% 46.7% 48.0%                  15.6%
head's age         35-44 86.1% 80.0% 75.9% 72.1% 68.0% 62.0% 63.6%                   9.0%
head's age         45-54 89.4% 85.0% 81.3% 77.2% 73.4% 67.6% 69.7%                   6.7%
head's age         55-64 91.2% 87.4% 84.1% 79.6% 75.9% 69.9% 72.2%                   5.4%
head's age   65 and over 92.7% 89.0% 85.3% 79.3% 75.2% 69.5% 70.6%                   4.5%
```

## The household file

`derived/panel/cohort_2017.parquet` on the server, one row per household and year (47,322,104 rows), sorted by household and year. Columns:

- `hhid`: household (its first FAMILYID in the panel, kept when it continues under a new one); `year`
- `status`: NC/SC, other state, missing, back later, gone for good
- `fid`: FAMILYID of that year's record; `state`, `county` (5-digit FIPS): where it is that year
- `moved`: at a new address since the year before (empty if not found the year before)
- `tenure` (owner, renter, unknown), `income` (dollars, FIND_DIV_1000 x 1000), `children`, `head_age` (band), `race` (first person): that year's record
- the same with `_2017`: the household in 2017; `income_quartile_2017`; `last_seen`: the last year it is found

Columns from that year's record are empty in years the household is not found.
