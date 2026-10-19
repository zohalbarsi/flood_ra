# Block assignment (counts and shares only)

106,518 block outlines; 7,658,013 distinct household coordinates in their bounding box (all years); 3,807,451 fall in a block, 22 of them on a line between blocks (given the lower GEOID). 1.7 minutes.

Family records (primary families and subfamilies) whose county (als2010 codes) is covered by the flood data. coordinates: usable latitude and longitude. in a block: the coordinates fall in a block outline. same tract / same BG: the block lies in the household's census tract / block group (share of those in a block); level P / other levels split that by GE_CENSUS_LEVEL_2010.

```
 year family records coordinates in a block same tract same BG same tract, level P same tract, other levels
 2007      1,472,589      100.0%      99.7%      96.0%   94.6%               99.6%                    71.7%
 2008      1,427,153      100.0%      99.8%      96.9%   95.8%               99.6%                    74.9%
 2009      1,552,177      100.0%      99.8%      97.1%   96.1%               99.6%                    76.1%
 2010      1,530,610      100.0%      99.8%      97.2%   96.2%               99.5%                    75.9%
 2011      1,510,178      100.0%      99.8%      97.2%   96.1%               99.5%                    75.0%
 2012      1,579,876      100.0%      99.8%      97.2%   96.3%               99.5%                    75.9%
 2013      1,825,756      100.0%      99.8%      97.2%   96.2%               99.3%                    77.4%
 2014      1,822,078      100.0%      99.8%      97.1%   96.1%               99.2%                    77.3%
 2015      1,852,942      100.0%      99.7%      95.5%   93.7%               99.0%                    76.2%
 2016      1,980,015      100.0%      99.7%      96.2%   94.6%               99.1%                    78.4%
 2017      2,127,812      100.0%      99.7%      96.2%   94.7%               99.4%                    77.3%
 2018      2,257,137      100.0%      99.9%      97.0%   95.7%               99.8%                    82.7%
 2019      2,324,094      100.0%      99.7%      96.3%   94.9%               99.7%                    76.7%
 2020      2,428,902      100.0%      99.9%      99.8%   99.7%              100.0%                    98.5%
 2021      2,517,765      100.0%      99.9%      99.8%   99.7%              100.0%                    98.1%
 2022      2,368,286      100.0%      99.9%      99.8%   99.7%              100.0%                    98.1%
 2023      2,152,630      100.0%      99.9%      99.9%   99.8%              100.0%                    99.0%
 2024      2,368,424      100.0%      99.9%      99.8%   99.8%              100.0%                    97.8%
 2025      2,969,847      100.0%      99.9%      99.7%   99.7%              100.0%                    97.4%
```

## Flood-county membership: county codes vs coordinates

All family records. by code: county (als2010 codes, the merge key) is a flood county. by coordinates: the point falls in a flood-county block. code only / coordinates only: in one but not the other. 2000 code: the Census 2000 county code (GE_CENSUS_COUNTY, empty from 2018) is a flood county; last column: in a flood block but not by the 2000 code.

```
 year   by code by coordinates      both code only coordinates only by 2000 code coordinates only vs 2000 code
 2007 1,472,589      1,618,159 1,468,436     4,153          149,723    1,623,550                         1,095
 2008 1,427,153      1,568,144 1,424,222     2,931          143,922    1,572,280                           947
 2009 1,552,177      1,707,992 1,549,300     2,877          158,692    1,712,013                           958
 2010 1,530,610      1,689,914 1,527,675     2,935          162,239    1,693,649                         1,020
 2011 1,510,178      1,667,798 1,507,076     3,102          160,722    1,672,010                         1,001
 2012 1,579,876      1,731,283 1,576,885     2,991          154,398    1,735,193                         1,000
 2013 1,825,756      1,994,110 1,822,573     3,183          171,537    1,998,397                         1,198
 2014 1,822,078      1,969,009 1,818,764     3,314          150,245    1,973,095                         1,295
 2015 1,852,942      1,848,866 1,847,587     5,355            1,279    1,852,907                         1,306
 2016 1,980,015      1,975,997 1,974,462     5,553            1,535    1,979,963                         1,575
 2017 2,127,812      2,123,435 2,122,040     5,772            1,395    2,127,753                         1,444
 2018 2,257,137      2,256,230 2,254,580     2,557            1,650    2,257,137                         1,650
 2019 2,324,094      2,319,016 2,317,564     6,530            1,452    2,307,722                        45,216
 2020 2,428,902      2,427,249 2,427,126     1,776              123                                           
 2021 2,517,765      2,516,145 2,516,021     1,744              124                                           
 2022 2,368,286      2,366,603 2,366,471     1,815              132                                           
 2023 2,152,630      2,151,550 2,151,397     1,233              153                                           
 2024 2,368,424      2,367,340 2,367,149     1,275              191                                           
 2025 2,969,847      2,968,465 2,968,177     1,670              288                                           
```
