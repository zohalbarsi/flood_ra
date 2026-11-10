# Do IDs change when people move? Name check within NC/SC (counts and shares only)

Primary families in NC/SC whose FAMILYID is in neither the next year's NC/SC file nor the step 07 file of records in other states (vanished). Their adults are looked up in the next year's NC/SC file by first name, last name and birth year (file year minus Age, one year either way). A match counts only if it is unique: no one else has that name and birth year in the first year (matchable), and exactly one person has it in the next year (found). Baseline: the same lookup for 1 in 20 households that kept their FAMILYID. Moves out of NC/SC are not covered (names are only in the NC/SC files).

## Households

vanished: share of primary families. found next year: share of vanished households with a matchable adult who is found; of which: found at the same address (record rebuilt in place), or in a FAMILYID that already existed (joined another household). found only the year after: not found next year, found the year after. old FAMILYID back: share of vanished households whose FAMILYID reappears the year after.

```
     years vanished with a matchable adult found next year of which same address of which in an older FAMILYID found only the year after old FAMILYID back the year after
2014->2015    16.6%                  62.3%           15.4%                 16.7%                         36.6%                     30.8%                            21.6%
2017->2018    12.2%                  60.0%           20.1%                 18.7%                         36.8%                     26.5%                            20.4%
2018->2019    10.9%                  59.4%           19.1%                 15.5%                         42.4%                     27.3%                            21.6%
```

## Adults

kept: adults of households that kept their FAMILYID. Found under the same person ID is how often the lookup finds someone who is there; found under another ID shows how often IDs change (or names coincide) for people who did not move. vanished: adults of vanished households; same person ID would mean the household changed FAMILYID but kept the person's ID.

```
     years kept: found, same person ID kept: found, other person ID kept: ambiguous vanished: found vanished: found, same person ID vanished: ambiguous
2014->2015                       91.7%                         0.2%            3.3%           15.5%                           40.8%                0.8%
2017->2018                       89.6%                         0.3%            4.6%           20.3%                           46.5%                1.4%
2018->2019                       90.0%                         0.2%            6.0%           19.1%                           39.9%                1.5%
```

How to read it: if 'vanished: found' is close to 'kept: found, same person ID', most vanished households are still in NC/SC under new IDs and could be linked by name; if it is far below, most are missing from the files.
