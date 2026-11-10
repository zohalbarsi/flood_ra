# MIGRATE: moves in, out and within NC and SC (aggregates)

Source: MIGRATE: Agostini, Young, Fitzpatrick, Garg and Pierson, "Inferring fine-grained migration patterns across the United States", NBER Working Paper 34263 (2025), arXiv:2503.20989; data from migrate.tech.cornell.edu. Files: 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019. The file for year t is read as moves between year t-1 and year t (check against the MIGRATE documentation). Block-group codes are read as text and padded to 12 digits. Figure: `output/figures/migrate_flows.png`; tables (state, county and block group, by year): `output/tables/migrate_*.csv`.

Notes: flood block groups found in MIGRATE: 2,261 of 2,261; block groups per group (2019): asu_s1: flooded, below median 1,085, flooded, median or more 1,085, not flooded 91, rest of NC 3,894; gfd: flooded, below median 203, flooded, median or more 204, not flooded 1,854, rest of NC 3,894; nc_fldex: flooded, below median 605, flooded, median or more 606, not flooded 1,020, rest of NC 3,894; sfincs: flooded, below median 582, flooded, median or more 582, not flooded 1,097, rest of NC 3,894

## Data checks (all flows in the US)

same block group: share of the total flow from a block group to itself. If it holds most of the flow, the matrix includes people who did not move and the total is close to the US population (about 310-330M in 2010-2019); otherwise it holds movers only. Here: it includes people who did not move, so rates below are shares of the population.

```
 year flows (rows) total flow same block group rows with flow < 1 min flow max flow codes not block groups
 2011        73.1M     309.3M            86.1%              83.0% 1.27e-26   30,173                      0
 2012        53.8M     311.6M            86.3%              80.1% 1.06e-25   31,457                      0
 2013        55.7M     313.9M            86.3%              80.8% 2.19e-25   35,825                      0
 2014        58.0M     316.1M            86.5%              82.0% 1.23e-25   41,910                      0
 2015        57.6M     318.4M            86.7%              81.8% 5.16e-25   35,588                      0
 2016        57.2M     320.7M            86.7%              81.8% 9.17e-24   46,856                      0
 2017        57.6M     323.1M            87.4%              82.8% 2.58e-25   49,870                      0
 2018        58.6M     325.1M            87.9%              83.9% 2.43e-26   53,036                      0
 2019        63.9M     326.8M            88.7%              86.0% 4.71e-25   53,155                      0
```

## NC and SC by year

population: all flows out of the state's block groups, staying included. moved within state: to another block group in the same state, as a share of it. out / in: people moving to / from other states; net = in - out.

```
 year state population moved within state out to other states in from other states    net out rate in rate
 2011    NC  9,574,586              11.1%             227,170              259,591 32,421     2.4%    2.7%
 2012    NC  9,658,913              10.8%             238,130              268,353 30,223     2.5%    2.8%
 2013    NC  9,751,810              11.0%             239,949              279,668 39,719     2.5%    2.9%
 2014    NC  9,846,717              10.8%             246,794              281,809 35,014     2.5%    2.9%
 2015    NC  9,937,295              10.9%             249,033              294,209 45,176     2.5%    3.0%
 2016    NC 10,037,218              11.0%             257,701              328,888 71,187     2.6%    3.3%
 2017    NC 10,161,802              10.0%             244,933              309,891 64,958     2.4%    3.0%
 2018    NC 10,275,758               9.4%             239,548              312,523 72,975     2.3%    3.0%
 2019    NC 10,391,358               8.7%             249,333              319,080 69,747     2.4%    3.1%
 2011    SC  4,635,846              10.5%             128,854              146,812 17,958     2.8%    3.2%
 2012    SC  4,672,655              10.6%             128,309              152,734 24,425     2.7%    3.3%
 2013    SC  4,719,027              10.1%             130,387              160,165 29,778     2.8%    3.4%
 2014    SC  4,766,469              10.1%             124,446              165,113 40,668     2.6%    3.5%
 2015    SC  4,826,858               9.9%             128,336              178,083 49,747     2.7%    3.7%
 2016    SC  4,896,006               9.7%             122,691              173,309 50,618     2.5%    3.5%
 2017    SC  4,963,031               9.3%             124,128              173,707 49,579     2.5%    3.5%
 2018    SC  5,027,102               8.6%             137,689              188,856 51,167     2.7%    3.8%
 2019    SC  5,091,702               7.6%             126,023              179,350 53,327     2.5%    3.5%
```

### Between NC and SC

```
 year NC to SC SC to NC
 2011   22,030   21,313
 2012   24,339   25,572
 2013   22,390   23,820
 2014   29,680   26,863
 2015   32,936   25,561
 2016   31,677   30,746
 2017   29,553   27,006
 2018   28,213   25,141
 2019   33,750   27,357
```

### Top 10 states people come from and go to, 2011-2019

Shares of all moves into (from) or out of (to) each state, from or to other states.

```
 rank NC from share NC to share SC from share SC to share
    1      VA 10.1%    SC 11.6%      NC 16.8%    NC 20.3%
    2      FL  9.5%    FL 10.9%      GA  9.4%    GA 12.8%
    3      SC  8.8%    VA  9.3%      FL  8.3%    FL  9.8%
    4      NY  8.0%    GA  6.8%      NY  6.1%    VA  6.0%
    5      GA  6.1%    TX  6.7%      VA  5.1%    TX  5.2%
    6      CA  5.6%    CA  5.0%      PA  4.4%    CA  4.4%
    7      TX  4.3%    NY  4.2%      CA  4.3%    NY  4.1%
    8      PA  4.3%    TN  4.0%      TX  4.0%    TN  3.6%
    9      NJ  3.6%    PA  3.3%      OH  3.8%    PA  2.6%
   10      MD  3.5%    MD  3.1%      NJ  2.9%    OH  2.2%
```

## Counties: leaving and entering, by year

Shares of the county population base (people who started the year in the county). Groups: the 34 NC counties in the flood data, the rest of NC, and SC.

### Left the county

```
 year NC flood counties rest of NC   SC
 2011              6.3%       5.5% 5.8%
 2012              6.3%       5.5% 5.7%
 2013              6.3%       5.5% 5.6%
 2014              6.3%       5.6% 5.5%
 2015              6.4%       5.6% 5.5%
 2016              6.5%       5.8% 5.3%
 2017              6.2%       5.5% 5.3%
 2018              5.8%       5.4% 5.4%
 2019              5.8%       5.3% 4.9%
```

### Came into the county

```
 year NC flood counties rest of NC   SC
 2011              6.6%       5.9% 6.2%
 2012              6.5%       5.9% 6.3%
 2013              6.6%       6.0% 6.3%
 2014              6.4%       6.1% 6.3%
 2015              6.6%       6.3% 6.6%
 2016              7.0%       6.7% 6.4%
 2017              6.5%       6.3% 6.3%
 2018              6.6%       6.1% 6.4%
 2019              6.4%       6.0% 5.9%
```

## Block groups by Florence flood exposure (NC flood counties)

Share of people who left their county during the year, by flood measure (step 02, block-group share flooded): not flooded (0), flooded below the median of flooded block groups, flooded at or above it; 'rest of NC' is every NC block group outside the flood data. If Florence displaced people, the flooded groups should stand out in 2019 (moves 2018-2019).

```
 measure  year not flooded flooded, below median flooded, median or more rest of NC
  asu_s1  2011        7.4%                  6.4%                    6.1%       5.5%
  asu_s1  2012        7.0%                  6.4%                    6.1%       5.5%
  asu_s1  2013        7.3%                  6.4%                    6.2%       5.5%
  asu_s1  2014        6.9%                  6.4%                    6.2%       5.6%
  asu_s1  2015        7.6%                  6.5%                    6.3%       5.6%
  asu_s1  2016        7.8%                  6.6%                    6.3%       5.8%
  asu_s1  2017        6.7%                  6.3%                    6.0%       5.5%
  asu_s1  2018        6.3%                  6.0%                    5.7%       5.4%
  asu_s1  2019        6.6%                  5.9%                    5.6%       5.3%
     gfd  2011        6.2%                  5.6%                    7.8%       5.5%
     gfd  2012        6.2%                  5.7%                    7.4%       5.5%
     gfd  2013        6.3%                  5.6%                    7.6%       5.5%
     gfd  2014        6.3%                  5.6%                    7.7%       5.6%
     gfd  2015        6.4%                  5.8%                    7.9%       5.6%
     gfd  2016        6.4%                  6.1%                    7.9%       5.8%
     gfd  2017        6.1%                  5.6%                    7.5%       5.5%
     gfd  2018        5.8%                  5.3%                    6.8%       5.4%
     gfd  2019        5.7%                  5.4%                    6.8%       5.3%
nc_fldex  2011        6.4%                  6.5%                    5.7%       5.5%
nc_fldex  2012        6.4%                  6.5%                    5.7%       5.5%
nc_fldex  2013        6.4%                  6.6%                    5.8%       5.5%
nc_fldex  2014        6.4%                  6.5%                    5.7%       5.6%
nc_fldex  2015        6.5%                  6.7%                    5.8%       5.6%
nc_fldex  2016        6.5%                  6.8%                    5.9%       5.8%
nc_fldex  2017        6.3%                  6.3%                    5.6%       5.5%
nc_fldex  2018        6.0%                  6.0%                    5.3%       5.4%
nc_fldex  2019        5.9%                  6.0%                    5.2%       5.3%
  sfincs  2011        6.7%                  5.9%                    5.9%       5.5%
  sfincs  2012        6.6%                  6.1%                    6.0%       5.5%
  sfincs  2013        6.6%                  6.1%                    6.1%       5.5%
  sfincs  2014        6.6%                  6.0%                    6.1%       5.6%
  sfincs  2015        6.7%                  6.2%                    6.1%       5.6%
  sfincs  2016        6.8%                  6.1%                    6.4%       5.8%
  sfincs  2017        6.5%                  5.8%                    5.9%       5.5%
  sfincs  2018        6.1%                  5.6%                    5.6%       5.4%
  sfincs  2019        6.1%                  5.5%                    5.5%       5.3%
```
