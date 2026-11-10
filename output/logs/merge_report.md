# Merge report (counts and shares only)

Geography from the **als2010** code columns (geo_family in config/settings.yaml), with the fallbacks described in scripts/04_merge.py. The flood tract file covers 34 counties.

family records: every family record in the study states (version: which file); primary families: PRIMARY_FAMILY_IND = 1, one per household. in flood counties: records whose county is covered by the flood data. The shares are of those: with a tract, with tract / block-group flood measures, placed in a block, and with block exposure usable (block_exposure_ok: rooftop-level geocode and the block lies in the record's county).

```
 year version family records primary families in flood counties  tract tract measures BG measures in a block block exposure ok
 2007    main      6,338,201        5,511,748         1,623,584  91.2%          91.2%       91.2%      99.6%             79.2%
 2008    main      6,156,253        5,324,259         1,572,315  91.2%          91.2%       91.2%      99.7%             81.1%
 2009    main      6,432,193        5,434,020         1,712,048  91.1%          91.1%       91.1%      99.7%             81.5%
 2010    main      6,382,507        5,434,749         1,693,688  90.8%          90.8%       90.8%      99.7%             81.6%
 2011    main      6,461,294        5,439,150         1,672,047  90.8%          90.8%       90.8%      99.7%             81.8%
 2012    main      6,656,799        5,486,557         1,735,231  91.5%          91.5%       91.5%      99.7%             82.7%
 2013    main      7,550,827        5,824,949         1,998,435  91.8%          91.8%       91.8%      99.7%             82.6%
 2014    main      7,363,788        5,702,246         1,973,146  92.8%          92.8%       92.8%      99.7%             83.8%
 2015    main      7,191,930        5,588,470         1,852,942 100.0%         100.0%      100.0%      99.7%             84.4%
 2016    main      7,733,064        5,732,735         1,980,015 100.0%         100.0%      100.0%      99.7%             85.6%
 2017    main      8,185,180        5,918,550         2,127,812 100.0%         100.0%      100.0%      99.7%             85.3%
 2018    main      8,714,501        6,092,135         2,257,137 100.0%         100.0%      100.0%      99.9%             83.6%
 2019    main      9,044,488        6,168,564         2,324,094 100.0%         100.0%      100.0%      99.7%             84.9%
 2020    main      9,388,392        6,341,921         2,428,902 100.0%         100.0%      100.0%      99.9%             85.7%
 2021    main      9,562,865        6,431,997         2,517,765 100.0%         100.0%      100.0%      99.9%             89.5%
 2022    main      9,143,006        6,316,806         2,368,286 100.0%         100.0%      100.0%      99.9%             89.1%
 2023     alt      8,384,057        5,978,389         2,152,630 100.0%         100.0%      100.0%      99.9%             88.6%
 2024    main      9,244,586        6,409,165         2,368,424 100.0%         100.0%      100.0%      99.9%             91.1%
```

## Who is in the flood counties, by each rule

no county code: share of records whose county code is unknown (000 or blank). Counts of records in the flood counties by: county code: the county code itself; via tract: the county part of the tract GEOID (the rule before this fix, which loses records whose tract is 000000); codes: the county code, else the Census 2000 county code up to 2017; coordinates: the point falls in a flood-county block. both / codes only / coordinates only compare the last two among records with both a county code and coordinates. chosen: in_flood_counties (codes, else coordinates); unknown: neither is known.

```
 year family records no county code county code via tract     codes coordinates      both codes only coordinates only    chosen unknown
 2007      6,338,201           9.6%   1,472,591 1,472,589 1,623,584   1,618,159 1,617,090      6,494            1,069 1,623,584      83
 2008      6,156,253           9.6%   1,427,153 1,427,153 1,572,315   1,568,144 1,567,229      5,086              915 1,572,315      79
 2009      6,432,193           9.7%   1,552,177 1,552,177 1,712,048   1,707,992 1,707,066      4,982              926 1,712,048      42
 2010      6,382,507           9.9%   1,530,610 1,530,610 1,693,688   1,689,914 1,688,926      4,762              988 1,693,688      38
 2011      6,461,294           9.9%   1,510,178 1,510,178 1,672,047   1,667,798 1,666,825      5,222              973 1,672,047      32
 2012      6,656,799           9.4%   1,579,876 1,579,876 1,735,231   1,731,283 1,730,310      4,921              973 1,735,231      28
 2013      7,550,827           9.1%   1,825,756 1,825,756 1,998,435   1,994,110 1,992,939      5,496            1,171 1,998,435      28
 2014      7,363,788           8.2%   1,822,078 1,822,078 1,973,146   1,969,009 1,967,755      5,391            1,254 1,973,146      26
 2015      7,191,930           0.0%   1,852,942 1,852,942 1,852,942   1,848,866 1,847,587      5,355            1,279 1,852,942       0
 2016      7,733,064           0.0%   1,980,015 1,980,015 1,980,015   1,975,997 1,974,462      5,553            1,535 1,980,015       0
 2017      8,185,180           0.0%   2,127,812 2,127,812 2,127,812   2,123,435 2,122,040      5,772            1,395 2,127,812       0
 2018      8,714,501           0.0%   2,257,137 2,257,137 2,257,137   2,256,230 2,254,580      2,557            1,650 2,257,137       0
 2019      9,044,488           0.0%   2,324,094 2,324,094 2,324,094   2,319,016 2,317,564      6,530            1,452 2,324,094       0
 2020      9,388,392           0.0%   2,428,902 2,428,902 2,428,902   2,427,249 2,427,126      1,776              123 2,428,902       0
 2021      9,562,865           0.0%   2,517,765 2,517,765 2,517,765   2,516,145 2,516,021      1,744              124 2,517,765       0
 2022      9,143,006           0.0%   2,368,286 2,368,286 2,368,286   2,366,603 2,366,471      1,815              132 2,368,286       0
 2023      8,384,057           0.0%   2,152,630 2,152,630 2,152,630   2,151,550 2,151,397      1,233              153 2,152,630       0
 2024      9,244,586           0.0%   2,368,424 2,368,424 2,368,424   2,367,340 2,367,149      1,275              191 2,368,424       0
```

## Where each record's geography comes from (records in the flood counties)

county from 2000 code / coordinates: the county code was unknown. tract from code: share with a valid tract code. tract from coordinates: tract code unknown, filled from the block (level P, block not in another county). no tract: still unknown. BG from coordinates: block-group code unknown, filled from a level-P block in the record's tract. Last two columns, all records: the block from the coordinates lies outside the record's county (its block measures are not joined), and of those, in another state.

```
 year in flood counties county from 2000 code county from coordinates tract from code tract from coordinates no tract BG from coordinates block outside county block in another state
 2007         1,623,584               150,993                       0           90.7%                  7,483  143,512               7,483                8,452                     15
 2008         1,572,315               145,162                       0           90.8%                  7,198  137,964               7,198                6,932                     17
 2009         1,712,048               159,871                       0           90.7%                  7,846  152,025               7,846                7,043                     13
 2010         1,693,688               163,078                       0           90.4%                  7,348  155,730               7,348                7,058                     13
 2011         1,672,047               161,869                       0           90.3%                  7,235  154,634               7,235                7,131                     15
 2012         1,735,231               155,355                       0           91.0%                  7,158  148,197               7,158                7,367                     14
 2013         1,998,435               172,679                       0           91.4%                  8,034  164,645               8,034                8,426                     12
 2014         1,973,146               151,068                       0           92.3%                  8,360  142,708               8,360                8,631                     14
 2015         1,852,942                     0                       0          100.0%                      0        0                   0                9,875                     15
 2016         1,980,015                     0                       0          100.0%                      0        0                   0                9,921                     13
 2017         2,127,812                     0                       0          100.0%                      0        0                   0                9,421                     15
 2018         2,257,137                     0                       0          100.0%                      0        0                   0                7,659                     25
 2019         2,324,094                     0                       0          100.0%                      0        0                   0                7,910                     19
 2020         2,428,902                     0                       0          100.0%                      0        0                   0                1,243                     15
 2021         2,517,765                     0                       0          100.0%                      0        0                   0                1,241                     14
 2022         2,368,286                     0                       0          100.0%                      0        0                   0                1,209                     14
 2023         2,152,630                     0                       0          100.0%                      0        0                   0                1,013                     15
 2024         2,368,424                     0                       0          100.0%                      0        0                   0                1,093                     10
```

## Codes vs coordinates, by geocode level (records in the flood counties)

GE_CENSUS_LEVEL_2010 (the dictionary gives no codes; P is taken as rooftop level), years pooled by period. tract code: share with a valid tract code. in a block: share of those whose coordinates fall in a block. same tract / same BG: share of those whose block lies in the record's tract / block group (BG: among records with a block-group code).

```
    years level    records tract code in a block same tract same BG
2007-2017     0    856,807      98.9%      99.9%      96.1%   94.2%
2007-2017     2     58,284      91.5%      99.6%      90.9%   87.7%
2007-2017     4    365,159      98.0%      99.8%      94.2%   91.0%
2007-2017     P 16,552,123      99.6%      99.9%      99.4%   99.0%
2007-2017     Z  2,108,890      44.2%      96.5%      49.5%   33.6%
2018-2019     0    304,173     100.0%      99.9%      97.6%   96.6%
2018-2019     2     42,980     100.0%      97.2%      66.3%   58.4%
2018-2019     4    116,054     100.0%      99.5%      76.5%   63.9%
2018-2019     P  3,863,875     100.0%     100.0%      99.8%   99.6%
2018-2019     X     81,475     100.0%      99.3%      66.9%   55.6%
2018-2019     Z    172,674     100.0%      97.2%      59.4%   44.1%
2020-2024     0    470,091     100.0%      99.9%      99.9%   99.8%
2020-2024     2     79,624     100.0%      99.8%      99.2%   99.1%
2020-2024     4    468,666     100.0%      99.8%      99.9%   99.8%
2020-2024     P 10,516,657     100.0%     100.0%     100.0%  100.0%
2020-2024     X    300,969     100.0%      98.8%      93.1%   91.2%
```

## Tract codes under each column set

valid code: share of all records with a well-formed tract code. tract match: share of the records whose tract-code county is a flood county that match a flood tract.

```
 year        columns valid code tract match
 2007         census      90.4%       47.4%
 2007 als2010 (used)      90.4%      100.0%
 2008         census      90.4%       47.0%
 2008 als2010 (used)      90.4%      100.0%
 2009         census      90.3%       47.5%
 2009 als2010 (used)      90.3%      100.0%
 2010         census      90.1%       47.2%
 2010 als2010 (used)      90.1%      100.0%
 2011         census      90.1%       46.3%
 2011 als2010 (used)      90.1%      100.0%
 2012         census      90.6%       46.4%
 2012 als2010 (used)      90.6%      100.0%
 2013         census      90.9%       47.0%
 2013 als2010 (used)      90.9%      100.0%
 2014         census      91.8%       46.8%
 2014 als2010 (used)      91.8%      100.0%
 2015         census     100.0%       45.8%
 2015 als2010 (used)     100.0%      100.0%
 2016         census     100.0%       46.1%
 2016 als2010 (used)     100.0%      100.0%
 2017         census     100.0%       46.1%
 2017 als2010 (used)     100.0%      100.0%
 2018         census       0.0%            
 2018 als2010 (used)     100.0%      100.0%
 2019         census       0.0%            
 2019 als2010 (used)     100.0%      100.0%
 2020         census       0.0%            
 2020 als2010 (used)     100.0%      100.0%
 2021         census       0.0%            
 2021 als2010 (used)     100.0%      100.0%
 2022         census       0.0%            
 2022 als2010 (used)     100.0%      100.0%
 2023         census       0.0%            
 2023 als2010 (used)     100.0%      100.0%
 2024         census       0.0%            
 2024 als2010 (used)     100.0%      100.0%
```
