# Household panel (counts and shares only)

Households: every FAMILYID that is a primary family in NC/SC in at least one year 2011-2024, followed in every year it appears anywhere in the US (other states: step 07). When a FAMILYID disappears, its adults are looked up the next year: if they all turn up under one new FAMILYID that holds no one else, it continues the household. One row per household and year; with several records in a year, the primary-family record, then the most recent. Geography from the 2010 ALS codes. Figure: `output/figures/panel_trends.png`; tables: `output/tables/panel_*.csv`.

- households: 16,258,139 (247,937 continue under a new FAMILYID at some point)
- household-years: 104,336,576
- households in NC/SC in 2017 (the cohort below): 7,021,463

## Where the households are, by year

other states: share of the year's households living outside the study states; under a new FAMILYID: share followed through a FAMILYID change.

```
 year households  in NC/SC other states under a new FAMILYID
 2011  6,253,582 5,839,333         6.6%                 0.0%
 2012  6,473,936 6,029,839         6.9%                 0.3%
 2013  7,084,614 6,600,322         6.8%                 0.4%
 2014  7,000,496 6,509,750         7.0%                 0.6%
 2015  6,878,175 6,372,324         7.4%                 0.8%
 2016  7,208,627 6,702,687         7.0%                 0.9%
 2017  7,535,702 7,021,463         6.8%                 0.9%
 2018  7,908,637 7,398,584         6.4%                 1.0%
 2019  8,080,491 7,565,112         6.4%                 1.1%
 2020  8,271,218 7,768,732         6.1%                 1.1%
 2021  8,308,054 7,836,957         5.7%                 1.2%
 2022  7,997,826 7,573,239         5.3%                 1.4%
 2023  7,399,211 7,023,439         5.1%                 1.5%
 2024  7,936,007 7,568,334         4.6%                 1.5%
```

## Households whose FAMILYID disappears

Households in the previous year's files whose FAMILYID is not in this year's, and what their adults' records show: continues new FAMILYID (all adults under one new FAMILYID with no one else; the household is followed), joined another household, split across households, or adults not found anywhere.

```
 year not found by familyid continues new familyid joined other household split adults not found
 2012               883,850                   1.9%                   2.9%  0.1%            95.0%
 2013               796,109                   2.3%                   4.3%  0.2%            93.2%
 2014             1,052,810                   1.9%                   3.2%  0.2%            94.8%
 2015             1,188,682                   1.9%                   3.1%  0.2%            94.9%
 2016             1,045,835                   2.1%                   4.1%  0.2%            93.6%
 2017               797,159                   2.2%                   3.9%  0.2%            93.6%
 2018               950,450                   2.4%                   4.3%  0.3%            93.0%
 2019               894,233                   2.0%                   3.5%  0.2%            94.3%
 2020             1,013,445                   2.0%                   3.6%  0.2%            94.2%
 2021             1,221,109                   1.9%                   3.3%  0.2%            94.6%
 2022             1,261,763                   1.8%                   3.2%  0.2%            94.8%
 2023             1,369,453                   1.4%                   2.6%  0.1%            95.8%
 2024               911,371                   1.5%                   3.9%  0.2%            94.5%
```

## Moves since the year before

Households found in both years. moved: new address (street, unit and ZIP, or PO box / route), among households with an address in both years; moved within NC/SC and left NC/SC: among households in NC/SC the year before; came to NC/SC: among households elsewhere the year before.

```
 year seen the year before moved moved within NC/SC left NC/SC came to NC/SC
 2012            5,386,642  6.8%               5.1%       0.7%         10.2%
 2013            5,697,436  7.3%               5.2%       0.8%         11.1%
 2014            6,053,955  7.5%               5.3%       0.8%         11.7%
 2015            5,837,802  8.3%               5.8%       0.8%         13.0%
 2016            5,859,621  9.2%               6.5%       0.9%         15.0%
 2017            6,433,062  6.5%               4.6%       0.6%         10.8%
 2018            6,613,692  8.9%               6.2%       0.9%         16.6%
 2019            7,037,430  6.3%               4.5%       0.6%         11.4%
 2020            7,095,467  6.7%               4.7%       0.6%         12.8%
 2021            7,083,339  7.4%               5.1%       0.8%         16.2%
 2022            7,077,403  7.1%               4.9%       0.8%         18.6%
 2023            6,656,088  6.4%               4.4%       0.7%         17.1%
 2024            6,508,498  4.9%               3.4%       0.5%         13.8%
```

### Where households leaving NC/SC go

All years; the last column counts moves between the 2018 and 2019 files (after Florence). States with fewer than 10 households are pooled.

```
state households of which 2018->2019 share
   FL     87,968               6,219 15.3%
   VA     57,819               4,019 10.1%
   GA     56,854               4,033  9.9%
   TX     38,526               2,717  6.7%
   TN     27,262               1,846  4.8%
   CA     27,101               1,864  4.7%
   NY     22,528               1,567  3.9%
   PA     21,134               1,418  3.7%
   OH     19,445               1,327  3.4%
   MD     16,922               1,194  3.0%
   CO     14,485               1,124  2.5%
   AL     11,295                 769  2.0%
   MI     11,274                 833  2.0%
   AZ     10,913                 799  1.9%
   WA     10,752                 790  1.9%
   IL     10,721                 739  1.9%
   NJ     10,200                 684  1.8%
   MA      9,201                 667  1.6%
   KY      8,631                 593  1.5%
   IN      8,450                 562  1.5%
   MO      7,090                 502  1.2%
   CT      5,773                 440  1.0%
   WV      5,409                 345  0.9%
   LA      5,375                 340  0.9%
   WI      5,016                 339  0.9%
   NV      4,335                 302  0.8%
   OR      4,302                 334  0.8%
   OK      4,192                 319  0.7%
   MN      4,127                 287  0.7%
   MS      3,915                 291  0.7%
   KS      3,785                 248  0.7%
   AR      3,387                 230  0.6%
   UT      3,233                 224  0.6%
   HI      3,119                 187  0.5%
   ME      2,913                 184  0.5%
   DC      2,909                 214  0.5%
   NH      2,775                 198  0.5%
   IA      2,715                 167  0.5%
   DE      2,685                 185  0.5%
   NM      2,550                 196  0.4%
   AK      1,960                 100  0.3%
   ID      1,943                 157  0.3%
   RI      1,716                 106  0.3%
   NE      1,549                 109  0.3%
   MT      1,495                  86  0.3%
   VT      1,440                  98  0.3%
   WY        760                  60  0.1%
   ND        746                  62  0.1%
   SD        721                  37  0.1%
```

## Households in NC/SC in 2017, followed 2011-2024

found and in NC/SC: shares of the 7,021,463 households. The 2017 households are measured wherever they live that year; 'all in NC/SC' is every panel household living in NC/SC that year (the cross-section). Owner share: codes 7-9 among 0-9 (unknown codes count as renters, as in step 06).

```
 year  found in NC/SC owner share: 2017 households owner share: all in NC/SC children: 2017 households children: all in NC/SC median income: 2017 households median income: all in NC/SC
 2011  56.9%    54.4%                        76.8%                     64.2%                     16.3%                  12.7%                         62,000                      48,000
 2012  61.1%    58.7%                        75.4%                     64.3%                     24.9%                  19.7%                         63,000                      50,000
 2013  66.7%    64.4%                        73.6%                     62.1%                     23.1%                  18.0%                         61,000                      49,000
 2014  69.7%    67.7%                        73.1%                     64.0%                     23.7%                  19.2%                         46,000                      38,000
 2015  73.0%    71.5%                        77.6%                     71.1%                     22.9%                  19.3%                         46,000                      40,000
 2016  85.1%    84.4%                        75.6%                     72.4%                     30.9%                  28.6%                         45,000                      42,000
 2017 100.0%   100.0%                        71.3%                     71.3%                     30.1%                  30.1%                         42,000                      42,000
 2018  87.4%    86.6%                        76.4%                     70.9%                     34.8%                  29.8%                         46,000                      42,000
 2019  82.3%    81.0%                        78.1%                     70.6%                     39.8%                  32.3%                         48,000                      43,000
 2020  78.3%    76.8%                        80.4%                     70.3%                     42.7%                  32.8%                         51,000                      44,000
 2021  73.4%    71.7%                        82.5%                     70.8%                     42.9%                  31.3%                         55,000                      47,000
 2022  68.9%    67.0%                        83.9%                     73.2%                     40.9%                  29.8%                         57,000                      49,000
 2023  62.7%    60.9%                        86.2%                     76.2%                     39.0%                  28.4%                         61,000                      53,000
 2024  64.4%    62.4%                        87.1%                     77.5%                     35.9%                  25.2%                         63,000                      55,000
```

## Tenure code changes at the same address

Households at the same address as the year before; share whose OWNER_RENTER_STATUS group changed. Jumps in single years point to Data Axle recoding rather than real changes.

```
 year same address owner to renter owner to unknown renter to owner unknown to owner renter to unknown unknown to renter
 2012    4,886,738            0.0%             0.4%            0.0%             1.8%              0.5%              0.2%
 2013    5,150,921            0.0%             0.3%            0.0%             2.7%              0.6%              0.2%
 2014    5,468,488            0.0%             0.3%            0.0%             1.6%              0.5%              0.2%
 2015    5,229,574            0.0%             0.6%            0.1%             7.1%              1.0%              1.0%
 2016    5,230,406            0.0%             0.2%            0.1%             2.2%              0.6%              0.1%
 2017    5,929,475            0.0%             0.3%            0.0%             1.3%              0.4%              0.1%
 2018    5,943,462            0.0%             0.3%            0.1%             2.1%              0.8%              0.1%
 2019    6,500,530            0.0%             2.1%            0.1%             2.7%              1.1%              4.5%
 2020    6,548,117            0.0%             0.2%            0.0%             2.4%              0.7%              0.1%
 2021    6,493,998            0.0%             0.2%            0.0%             3.5%              1.1%              0.1%
 2022    6,489,454            0.0%             0.2%            0.0%             2.4%              0.8%              0.1%
 2023    6,177,709            0.0%             0.2%            0.0%             2.6%              0.8%              0.1%
 2024    6,137,863            0.0%             0.4%            0.0%             2.3%              0.8%              0.2%
```
