#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import io

from activityio._util import xml_reading


data = '''<?xml version="1.0" encoding="UTF-8"?>
<TrainingCenterDatabase>
  <Activities>
    <Activity Sport="Biking">
      <Id>2015-03-24T15:19:06.000Z</Id>
      <Lap StartTime="2015-03-24T15:19:06.000Z">
        <TotalTimeSeconds>946.253</TotalTimeSeconds>
        <DistanceMeters>6984.14</DistanceMeters>
        <MaximumSpeed>10.291000366210938</MaximumSpeed>
        <Calories>162</Calories>
        <Intensity>Active</Intensity>
        <Cadence>86</Cadence>
        <TriggerMethod>Manual</TriggerMethod>
        <Track>
          <Trackpoint>
            <Time>2015-03-24T15:19:06.000Z</Time>
            <Position>
              <LatitudeDegrees>52.759598745033145</LatitudeDegrees>
              <LongitudeDegrees>-1.2168367579579353</LongitudeDegrees>
            </Position>
            <DistanceMeters>1.7400000095367432</DistanceMeters>
            <Cadence>5</Cadence>
            <Extensions>
              <TPX xmlns="http://www.garmin.com/xmlschemas/ActivityExtension/v2">
                <Watts>30</Watts>
              </TPX>
            </Extensions>
          </Trackpoint>
          <Trackpoint>
            <Time>2015-03-24T15:19:07.000Z</Time>
            <Position>
              <LatitudeDegrees>52.75961358100176</LatitudeDegrees>
              <LongitudeDegrees>-1.2168002966791391</LongitudeDegrees>
            </Position>
            <DistanceMeters>3.7100000381469727</DistanceMeters>
            <Cadence>14</Cadence>
            <Extensions>
              <TPX xmlns="http://www.garmin.com/xmlschemas/ActivityExtension/v2">
                <Watts>30</Watts>
              </TPX>
            </Extensions>
          </Trackpoint>
        </Track>
      </Lap>
    </Activity>
  </Activities>
</TrainingCenterDatabase>'''


def test_parsing():
    fakefile = io.StringIO(data)

    trkpts = [xml_reading.recursive_text_extract(trkpt)
              for trkpt in xml_reading.gen_nodes(fakefile, ('Trackpoint',))]

    assert len(trkpts) == 2
    t1, t2 = trkpts
    assert len(t1) == 6 and len(t2) == 6
    assert t1['Watts'] == '30' and t2['Watts'] == '30'
    assert t1['Time'] == '2015-03-24T15:19:06.000Z'
    assert t2['Time'] == '2015-03-24T15:19:07.000Z'
