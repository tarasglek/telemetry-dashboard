#Telemetry Dashboard

Generate static files for a telemetry dashboard.


#How to Run

You'll need to have `mango` set up in your .ssh_config to connect you to the hadoop node where you'll run jydoop from.

```
Run `script/bootstrap`
Serve the `html/` dir
```

##Histogram View
There are x fields to narrow query by

have a category table that stores category tree:
Each node has a unique id
Level1 Product: Firefox|Fennec|Thunderbird
Level2 Platform: Windows|Linux
Level3 etc


size of this table can be kept in check by reducing common videocards to a family name, etc
Can also customize what shows up under different levels..For example we could restrict tb, to have less childnodes.

Store the tree in a table, but keep it read  into memory for queries, inserting new records

Then have a histogram table where
columns: histogram_id | category_id | value
where histogram_id is id like SHUTDOWN_OK, category id is a key from category table, value is the sum of histograms in that category...can be represented with some binary value


##Misc
Evolution can be implemented by adding a build_date field to histogram table

TODO:
How big would the category tree table be..surely there is a finite size for that

histogram table would be |category_table| * |number of histograms|, pretty compact

### Map + Reduce
Mapper should turn each submission into
<key> <data> which looks like
buildid/channel/reason/appName/appVersion/OS/osVersion/arch {histograms:{A11Y_CONSUMERS:{histogram_data}, ...} simpleMeasures:{firstPaint:[100,101,1000...]}}
Where key identifies where in the filter tree the data should live..Note a single packet could produce more than 1 such entry if we want to get into detailed breakdowns of gfxCard vs some FX UI animation histogram

Reducer would then take above data and sum up histograms + append to simple measure lists based on key


This should produce a fairly small file per day per channel(~200 records). Which will then be quick to pull out and merge into the per-build-per-histogram-json that can be rsynced to some webserver. This basically a final iterative REDUCE on top of map-reduce for new data. Hadoop does not feel like the right option for that, but I could be wrong.

###todo:

* oneline local testing using Jython's FileDriver.py

