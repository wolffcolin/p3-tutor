# 0001 - Filtering and basic index access

## Objective
Understand the difference between rows examined and rows returned, and use selectivity for rough row-count estimates.

## What the learner showed
The learner could write a simple WHERE query and compute that 5% of 20,000 rows is 1,000 rows. They could describe an index as an access path but still sometimes assumed an index was always faster.

## Evidence
In a worked example, they calculated the filtered result cardinality correctly but needed prompting to distinguish that result count from the number of table rows examined by a full scan.

## Implications for next time
Start from this filtering knowledge and move to joins. Use concrete input sizes and a small example to compare how nested loops, indexed lookups, hash tables, and ordering change work.
