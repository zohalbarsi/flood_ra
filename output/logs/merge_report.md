# Merge report (counts and shares only)

Merge keys built from the **als2010** columns (geo_family in config/settings.yaml). The flood tract file covers 34 counties.

households: study-state households in the converted file (version: which file). valid code: a well-formed tract code. in flood counties: the county appears in the flood data. tract / BG match: share of the in-county households whose tract / block group is in the flood data. block found: share of the in-county households placed in a block by step 03 (details in block_assignment.md).

```
 year version        columns households valid code in flood counties tract match BG match block found
 2007    main         census  4,387,393     100.0%             37.0%       43.0%    41.6%            
 2007    main als2010 (used)  4,387,393     100.0%             33.6%      100.0%   100.0%       99.7%
 2008    main         census  4,252,381     100.0%             37.0%       42.7%    41.3%            
 2008    main als2010 (used)  4,252,381     100.0%             33.6%      100.0%   100.0%       99.8%
 2009    main         census  4,577,802     100.0%             37.4%       43.0%    41.6%            
 2009    main als2010 (used)  4,577,802     100.0%             33.9%      100.0%   100.0%       99.8%
 2010    main         census  4,516,391     100.0%             37.5%       42.7%    41.3%            
 2010    main als2010 (used)  4,516,391     100.0%             33.9%      100.0%   100.0%       99.8%
 2011    main         census  4,479,268     100.0%             37.3%       41.8%    40.5%            
 2011    main als2010 (used)  4,479,268     100.0%             33.7%      100.0%   100.0%       99.8%
 2012    main         census  4,627,818     100.0%             37.5%       42.3%    40.9%            
 2012    main als2010 (used)  4,627,818     100.0%             34.1%      100.0%   100.0%       99.8%
 2013    main         census  5,279,508     100.0%             37.9%       43.0%    41.6%            
 2013    main als2010 (used)  5,279,508     100.0%             34.6%      100.0%   100.0%       99.8%
 2014    main         census  5,205,927     100.0%             37.9%       43.2%    41.8%            
 2014    main als2010 (used)  5,205,927     100.0%             35.0%      100.0%   100.0%       99.8%
 2015    main         census  4,954,311     100.0%             37.4%       45.8%    44.4%            
 2015    main als2010 (used)  4,954,311     100.0%             37.4%      100.0%   100.0%       99.7%
 2016    main         census  5,290,248     100.0%             37.4%       46.1%    44.7%            
 2016    main als2010 (used)  5,290,248     100.0%             37.4%      100.0%   100.0%       99.7%
 2017    main         census  5,625,111     100.0%             37.8%       46.1%    44.7%            
 2017    main als2010 (used)  5,625,111     100.0%             37.8%      100.0%   100.0%       99.7%
 2018    main         census  6,005,534       0.0%              0.0%                                 
 2018    main als2010 (used)  6,005,534     100.0%             37.6%      100.0%   100.0%       99.9%
 2019    main         census  6,180,010       0.0%              0.0%                                 
 2019    main als2010 (used)  6,180,010     100.0%             37.6%      100.0%   100.0%       99.7%
 2020    main         census  6,474,156       0.0%              0.0%                                 
 2020    main als2010 (used)  6,474,156     100.0%             37.5%      100.0%   100.0%       99.9%
 2021    main         census  6,700,820       0.0%              0.0%                                 
 2021    main als2010 (used)  6,700,820     100.0%             37.6%      100.0%   100.0%       99.9%
 2022    main         census  6,295,228       0.0%              0.0%                                 
 2022    main als2010 (used)  6,295,228     100.0%             37.6%      100.0%   100.0%       99.9%
 2023     alt         census  5,717,475       0.0%              0.0%                                 
 2023     alt als2010 (used)  5,717,475     100.0%             37.7%      100.0%   100.0%       99.9%
 2024    main         census  6,299,994       0.0%              0.0%                                 
 2024    main als2010 (used)  6,299,994     100.0%             37.6%      100.0%   100.0%       99.9%
 2025    main         census  7,844,644       0.0%              0.0%                                 
 2025    main als2010 (used)  7,844,644     100.0%             37.9%      100.0%   100.0%       99.9%
```
