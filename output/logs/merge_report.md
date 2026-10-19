# Merge report (counts and shares only)

Merge keys built from the **als2010** columns (geo_family in config/settings.yaml). The flood tract file covers 34 counties.

family records: every family record in the study states (version: which file), primary families and subfamilies alike; primary families: those with PRIMARY_FAMILY_IND = 1, one per household. Shares are of all family records. valid code: a well-formed tract code. in flood counties: the county appears in the flood data. tract / BG match: share of the in-county records whose tract / block group is in the flood data. block found: share of the in-county records placed in a block by step 03 (details in block_assignment.md).

```
 year version        columns family records primary families valid code in flood counties tract match BG match block found
 2007    main         census      6,338,201        5,511,748      90.4%             23.2%       47.4%    45.9%            
 2007    main als2010 (used)      6,338,201        5,511,748      90.4%             23.2%      100.0%   100.0%       99.7%
 2008    main         census      6,156,253        5,324,259      90.4%             23.2%       47.0%    45.5%            
 2008    main als2010 (used)      6,156,253        5,324,259      90.4%             23.2%      100.0%   100.0%       99.8%
 2009    main         census      6,432,193        5,434,020      90.3%             24.1%       47.5%    45.9%            
 2009    main als2010 (used)      6,432,193        5,434,020      90.3%             24.1%      100.0%   100.0%       99.8%
 2010    main         census      6,382,507        5,434,749      90.1%             24.0%       47.2%    45.7%            
 2010    main als2010 (used)      6,382,507        5,434,749      90.1%             24.0%      100.0%   100.0%       99.8%
 2011    main         census      6,461,294        5,439,150      90.1%             23.4%       46.3%    44.8%            
 2011    main als2010 (used)      6,461,294        5,439,150      90.1%             23.4%      100.0%   100.0%       99.8%
 2012    main         census      6,656,799        5,486,557      90.6%             23.7%       46.4%    45.0%            
 2012    main als2010 (used)      6,656,799        5,486,557      90.6%             23.7%      100.0%   100.0%       99.8%
 2013    main         census      7,550,827        5,824,949      90.9%             24.2%       47.0%    45.5%            
 2013    main als2010 (used)      7,550,827        5,824,949      90.9%             24.2%      100.0%   100.0%       99.8%
 2014    main         census      7,363,788        5,702,246      91.8%             24.7%       46.8%    45.3%            
 2014    main als2010 (used)      7,363,788        5,702,246      91.8%             24.7%      100.0%   100.0%       99.8%
 2015    main         census      7,191,930        5,588,470     100.0%             25.8%       45.8%    44.4%            
 2015    main als2010 (used)      7,191,930        5,588,470     100.0%             25.8%      100.0%   100.0%       99.7%
 2016    main         census      7,733,064        5,732,735     100.0%             25.6%       46.1%    44.7%            
 2016    main als2010 (used)      7,733,064        5,732,735     100.0%             25.6%      100.0%   100.0%       99.7%
 2017    main         census      8,185,180        5,918,550     100.0%             26.0%       46.1%    44.7%            
 2017    main als2010 (used)      8,185,180        5,918,550     100.0%             26.0%      100.0%   100.0%       99.7%
 2018    main         census      8,714,501        6,092,135       0.0%              0.0%                                 
 2018    main als2010 (used)      8,714,501        6,092,135     100.0%             25.9%      100.0%   100.0%       99.9%
 2019    main         census      9,044,488        6,168,564       0.0%              0.0%                                 
 2019    main als2010 (used)      9,044,488        6,168,564     100.0%             25.7%      100.0%   100.0%       99.7%
 2020    main         census      9,388,392        6,341,921       0.0%              0.0%                                 
 2020    main als2010 (used)      9,388,392        6,341,921     100.0%             25.9%      100.0%   100.0%       99.9%
 2021    main         census      9,562,865        6,431,997       0.0%              0.0%                                 
 2021    main als2010 (used)      9,562,865        6,431,997     100.0%             26.3%      100.0%   100.0%       99.9%
 2022    main         census      9,143,006        6,316,806       0.0%              0.0%                                 
 2022    main als2010 (used)      9,143,006        6,316,806     100.0%             25.9%      100.0%   100.0%       99.9%
 2023     alt         census      8,384,057        5,978,389       0.0%              0.0%                                 
 2023     alt als2010 (used)      8,384,057        5,978,389     100.0%             25.7%      100.0%   100.0%       99.9%
 2024    main         census      9,244,586        6,409,165       0.0%              0.0%                                 
 2024    main als2010 (used)      9,244,586        6,409,165     100.0%             25.6%      100.0%   100.0%       99.9%
 2025    main         census     11,222,316        6,966,597       0.0%              0.0%                                 
 2025    main als2010 (used)     11,222,316        6,966,597     100.0%             26.5%      100.0%   100.0%       99.9%
```
