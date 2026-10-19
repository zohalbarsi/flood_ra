# Merge report (counts and shares only)

Merge keys built from the **als2010** columns (geo_family in config/settings.yaml). The flood tract file covers 34 counties.

households: study-state households in the converted file (version: which file). valid code: a well-formed tract code. in flood counties: the county appears in the flood data. tract / BG match: share of the in-county households whose tract / block group is in the flood data. block found: share of the in-county households placed in a block by step 03 (details in block_assignment.md).

```
 year version        columns households valid code in flood counties tract match BG match block found
 2007    main         census  6,338,201     100.0%             25.6%       43.0%    41.6%            
 2007    main als2010 (used)  6,338,201     100.0%             23.2%      100.0%   100.0%       99.7%
 2008    main         census  6,156,253     100.0%             25.5%       42.7%    41.3%            
 2008    main als2010 (used)  6,156,253     100.0%             23.2%      100.0%   100.0%       99.8%
 2009    main         census  6,432,193     100.0%             26.6%       43.0%    41.6%            
 2009    main als2010 (used)  6,432,193     100.0%             24.1%      100.0%   100.0%       99.8%
 2010    main         census  6,382,507     100.0%             26.5%       42.7%    41.3%            
 2010    main als2010 (used)  6,382,507     100.0%             24.0%      100.0%   100.0%       99.8%
 2011    main         census  6,461,294     100.0%             25.9%       41.8%    40.5%            
 2011    main als2010 (used)  6,461,294     100.0%             23.4%      100.0%   100.0%       99.8%
 2012    main         census  6,656,799     100.0%             26.1%       42.3%    40.9%            
 2012    main als2010 (used)  6,656,799     100.0%             23.7%      100.0%   100.0%       99.8%
 2013    main         census  7,550,827     100.0%             26.5%       43.0%    41.6%            
 2013    main als2010 (used)  7,550,827     100.0%             24.2%      100.0%   100.0%       99.8%
 2014    main         census  7,363,788     100.0%             26.8%       43.2%    41.8%            
 2014    main als2010 (used)  7,363,788     100.0%             24.7%      100.0%   100.0%       99.8%
 2015    main         census  7,191,930     100.0%             25.8%       45.8%    44.4%            
 2015    main als2010 (used)  7,191,930     100.0%             25.8%      100.0%   100.0%       99.7%
 2016    main         census  7,733,064     100.0%             25.6%       46.1%    44.7%            
 2016    main als2010 (used)  7,733,064     100.0%             25.6%      100.0%   100.0%       99.7%
 2017    main         census  8,185,180     100.0%             26.0%       46.1%    44.7%            
 2017    main als2010 (used)  8,185,180     100.0%             26.0%      100.0%   100.0%       99.7%
 2018    main         census  8,714,501       0.0%              0.0%                                 
 2018    main als2010 (used)  8,714,501     100.0%             25.9%      100.0%   100.0%       99.9%
 2019    main         census  9,044,488       0.0%              0.0%                                 
 2019    main als2010 (used)  9,044,488     100.0%             25.7%      100.0%   100.0%       99.7%
 2020    main         census  9,388,392       0.0%              0.0%                                 
 2020    main als2010 (used)  9,388,392     100.0%             25.9%      100.0%   100.0%       99.9%
 2021    main         census  9,562,865       0.0%              0.0%                                 
 2021    main als2010 (used)  9,562,865     100.0%             26.3%      100.0%   100.0%       99.9%
 2022    main         census  9,143,006       0.0%              0.0%                                 
 2022    main als2010 (used)  9,143,006     100.0%             25.9%      100.0%   100.0%       99.9%
 2023     alt         census  8,384,057       0.0%              0.0%                                 
 2023     alt als2010 (used)  8,384,057     100.0%             25.7%      100.0%   100.0%       99.9%
 2024    main         census  9,244,586       0.0%              0.0%                                 
 2024    main als2010 (used)  9,244,586     100.0%             25.6%      100.0%   100.0%       99.9%
 2025    main         census 11,222,316       0.0%              0.0%                                 
 2025    main als2010 (used) 11,222,316     100.0%             26.5%      100.0%   100.0%       99.9%
```
