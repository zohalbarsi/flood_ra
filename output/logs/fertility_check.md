# Births: infoUSA vs ACS, NC and SC (counts and rates only)

infoUSA has no birth records. A birth can only show up as a household's children count (CHILDRENHHCOUNT; 0 when CHILDREN_IND says no children) rising from one year's file to the next. **infoUSA:** primary-family households in the state in year t that were also in the household panel in t-1 (step 08, so households continuing under a new FAMILYID count), with a known count in both years; children added = sum of the increases. **ACS:** women 15-50 with a birth in the past 12 months (B13002, 1-year estimates; twins count once), per 1,000 households (B25003). The ACS 1-year 2020 release does not exist.

Years with both measures, outside the 2012 and 2016 model changes (2013, 2014, 2015, 2017, 2018, 2019, 2021, 2022, 2023, 2024), NC+SC: infoUSA adds 39.3 children per 1,000 households a year, the ACS records 31.0 births per 1,000 households (infoUSA / ACS = 1.27).

## Children added (infoUSA) vs births (ACS)

```
 year state households, both years children added per 1,000 ACS births ACS per 1,000 infoUSA / ACS
2012*    NC              3,164,330        351,474     111.1    135,270          36.3          3.06
 2013    NC              3,270,261         14,600       4.5    118,248          31.5          0.14
 2014    NC              3,431,711         28,747       8.4    121,511          32.1          0.26
 2015    NC              3,291,104         43,243      13.1    119,725          31.1          0.42
2016*    NC              3,214,487        904,983     281.5    120,067          30.9          9.10
 2017    NC              3,451,939        322,234      93.3    127,760          32.3          2.89
 2018    NC              3,505,083        109,079      31.1    119,280          29.7          1.05
 2019    NC              3,675,087        447,761     121.8    129,358          32.0          3.81
 2020    NC              3,690,523        218,849      59.3                                       
 2021    NC              3,769,923        129,300      34.3    119,762          28.7          1.20
 2022    NC              3,833,253        209,520      54.7    129,267          30.1          1.82
 2023    NC              3,622,339         74,922      20.7    131,195          29.9          0.69
 2024    NC              3,540,282         59,507      16.8    136,689          30.4          0.55
2012*    SC              1,445,833        162,172     112.2     60,734          34.0          3.30
 2013    SC              1,495,265          7,929       5.3     58,531          32.6          0.16
 2014    SC              1,542,952         14,451       9.4     56,055          30.7          0.31
 2015    SC              1,498,388         20,133      13.4     61,316          33.0          0.41
2016*    SC              1,503,515        418,364     278.3     60,080          32.0          8.70
 2017    SC              1,645,648        137,426      83.5     66,875          35.1          2.38
 2018    SC              1,656,939         48,578      29.3     63,951          33.2          0.88
 2019    SC              1,749,210        200,786     114.8     63,576          32.2          3.57
 2020    SC              1,765,577         81,015      45.9                                       
 2021    SC              1,744,225         48,475      27.8     60,830          29.7          0.94
 2022    SC              1,752,283         74,592      42.6     63,426          29.7          1.43
 2023    SC              1,732,062         27,181      15.7     67,375          30.9          0.51
 2024    SC              1,715,806         24,493      14.3     67,181          30.2          0.47
2012* NC+SC              4,610,163        513,646     111.4    196,004          35.5          3.14
 2013 NC+SC              4,765,526         22,529       4.7    176,779          31.8          0.15
 2014 NC+SC              4,974,663         43,198       8.7    177,566          31.6          0.27
 2015 NC+SC              4,789,492         63,376      13.2    181,041          31.8          0.42
2016* NC+SC              4,718,002      1,323,347     280.5    180,147          31.3          8.97
 2017 NC+SC              5,097,587        459,660      90.2    194,635          33.2          2.71
 2018 NC+SC              5,162,022        157,657      30.5    183,231          30.8          0.99
 2019 NC+SC              5,424,297        648,547     119.6    192,934          32.0          3.73
 2020 NC+SC              5,456,100        299,864      55.0                                       
 2021 NC+SC              5,514,148        177,775      32.2    180,592          29.0          1.11
 2022 NC+SC              5,585,536        284,112      50.9    192,693          29.9          1.70
 2023 NC+SC              5,354,401        102,103      19.1    198,570          30.2          0.63
 2024 NC+SC              5,256,088         84,000      16.0    203,870          30.3          0.53
```

\* Data Axle changed its children model: the share of households with children steps up (10% to 20% in 2012, to 30% in 2016), so most of the increase in these years is recoding, not births.

## Detail (per 1,000 households)

More children: households whose count rose. Flag turned on: households whose CHILDREN_IND went from 0 to 1. Added, same address: children added among households at the same address both years (moves can rebuild a record). Removed: the sum of decreases (children aging out or leaving, or recoding). Last column: an ACS check (about 50-60 is normal).

```
 year state more children flag turned on added, same address removed ACS births per 1,000 women 15-50
2012*    NC          91.9           79.4               119.0     9.5                             56.7
 2013    NC           4.2            2.9                 4.1    14.7                             49.4
 2014    NC           8.0            8.4                 8.2    16.5                             50.6
 2015    NC          12.7            7.8                13.2    19.2                             49.7
2016*    NC         190.1          124.3               292.9    12.0                             49.2
 2017    NC          79.5           44.6                96.3    22.8                             52.0
 2018    NC          27.7           20.2                31.2    29.1                             48.3
 2019    NC          95.3           37.3               124.1    31.6                             51.8
 2020    NC          52.7           31.3                58.6    34.5                                 
 2021    NC          29.6            6.7                33.9    37.9                             48.1
 2022    NC          49.9           21.1                56.1    34.8                             51.3
 2023    NC          18.4            5.5                20.1    37.0                             51.4
 2024    NC          15.3            7.2                16.3    38.2                             52.2
2012*    SC          91.5           81.5               119.1     9.9                             53.5
 2013    SC           5.0            3.2                 4.9    15.9                             51.3
 2014    SC           8.9            9.4                 9.1    17.3                             49.0
 2015    SC          12.9            7.3                13.2    20.7                             53.6
2016*    SC         189.2          119.1               288.0    13.5                             51.8
 2017    SC          69.2           37.1                85.3    20.7                             57.3
 2018    SC          25.7           18.7                29.0    31.2                             54.6
 2019    SC          90.2           40.4               116.4    32.8                             53.5
 2020    SC          40.4           21.6                44.8    34.3                                 
 2021    SC          23.8            5.3                27.3    37.6                             51.0
 2022    SC          38.6           16.1                43.3    36.2                             52.8
 2023    SC          13.7            4.3                15.0    32.6                             54.7
 2024    SC          12.7            6.4                13.8    39.0                             53.8
2012* NC+SC          91.8           80.1               119.0     9.7                             55.7
 2013 NC+SC           4.5            3.0                 4.4    15.1                             50.0
 2014 NC+SC           8.3            8.7                 8.5    16.8                             50.1
 2015 NC+SC          12.8            7.6                13.2    19.7                             50.9
2016* NC+SC         189.8          122.6               291.4    12.5                             50.1
 2017 NC+SC          76.2           42.2                92.7    22.1                             53.7
 2018 NC+SC          27.1           19.7                30.5    29.8                             50.3
 2019 NC+SC          93.7           38.3               121.6    32.0                             52.3
 2020 NC+SC          48.7           28.2                54.1    34.4                                 
 2021 NC+SC          27.8            6.2                31.8    37.8                             49.0
 2022 NC+SC          46.4           19.5                52.1    35.2                             51.8
 2023 NC+SC          16.8            5.1                18.5    35.6                             52.5
 2024 NC+SC          14.5            6.9                15.4    38.5                             52.7
```

## Reading the comparison

- The count also rises when children move in (new partners, relatives) and when Data Axle's model updates a household; a birth in the same year a child leaves the household is missed.
- Timing differs: the ACS counts births in the 12 months before the interview (spread over year t); infoUSA, changes between the t-1 and t files.
- Households seen only in t (new households, including new parents who set up a home) are not counted.

Census tables cached in `benchmarks/`.
