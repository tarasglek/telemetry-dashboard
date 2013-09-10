try:
    import simplejson as json
    print "Using simplejson for faster json parsing"
except ImportError:
    import json
import sys
import telemetryutils
import jydoop
import __builtin__

verbose = False

SPECS = "scripts/histogram_specs.json"
histogram_specs = json.loads(
    jydoop.getResource(SPECS))

# hack, get an arbiratry histogram with 1..30000 exponential histogram dimensions
SIMPLE_MEASURES_ = histogram_specs['HTTP_SUB_OPEN_TO_FIRST_RECEIVED']

def map(uid, line, context):
    global histogram_specs

    payload = json.loads(line)
    try:
        i = payload['info']
        channel = i.get('appUpdateChannel', "too_old")
        OS = i['OS']
        appName = i['appName']
        reason = i['reason']
        osVersion = str(i['version'])
        #only care about major versions
        appVersion = i['appVersion'].split('.')[0]
        arch = i['arch']
        buildDate = i['appBuildID'][:8]
    except (KeyError, IndexError, UnicodeEncodeError):
        msg = "error while unpacking the payload"
        print >> sys.stderr, msg
        return

    # TODO: histogram_specs should specify the list of versions/channels we
    #       care about
    if not channel in ['release', 'aurora', 'nightly', 'beta', 'nightly-ux']:
        return

    # todo combine OS + osVersion + santize on crazy platforms like linux to
    #      reduce pointless choices
    if OS == "Linux":
        osVersion = osVersion[:3]

    path = (buildDate, reason, appName, OS, osVersion, arch)
    histograms = payload.get('histograms', {})

    for h_name, h_values in histograms.iteritems():
        bucket2index = histogram_specs.get(h_name, None)
        if bucket2index is None:
            if verbose:
                msg = "%s definition not found in %s" % (h_name, SPECS)
                print >> sys.stderr, msg
            continue
        else:
            bucket2index = bucket2index[0]

        # most buckets contain 0s, so preallocation is a significant win
        outarray = [0] * (len(bucket2index) + 2)
        error = False
        if h_values is None:
            msg = "h_values is None in map"
            print >> sys.stderr, msg
            continue

        values = h_values.get('values', None)
        if values is None:
            continue
        for bucket, value in values.iteritems():
            index = bucket2index.get(bucket, None)
            if index is None:
                #print "%s's does not feature %s bucket in schema"
                #    % (h_name, bucket)
                error = True
                break
            outarray[index] = value
        if error:
            if verbose:
                msg = "Invalid bucket '%s' in %s" % (bucket, h_name)
                print >> sys.stderr, msg
            continue

        histogram_sum = h_values.get('sum', None)
        if histogram_sum is None:
            msg = "histogram_sum is None in map"
            print >> sys.stderr, msg
            continue
        outarray[-2] = histogram_sum
        outarray[-1] = 1        # count
        context.write((channel, appVersion, h_name), {path: outarray})
        
    rawSimpleMeasurements = payload.get('simpleMeasurements', {})
    simpleMeasurements = {}
    # flatten subdicts
    for sm_name, sm_value in rawSimpleMeasurements.iteritems():
        if type(sm_value) == dict:
            for sub_name, sub_value in sm_value.iteritems():
                simpleMeasurements[sm_name + "_" + sub_name] = sub_value
        else:
            simpleMeasurements[sm_name] = sm_value

    for sm_name, sm_value in simpleMeasurements.iteritems():
        if type(sm_value) != int:
            if verbose:
                print >> sys.stderr, ("%s is not a value type for simpleMeasurements.%s" % 
                                  (type(sm_value), sm_name))
            continue
        buckets = SIMPLE_MEASURES_[1]
        
        # most buckets contain 0s, so preallocation is a significant win
        outarray = [0] * (len(buckets) + 2)
        for i in reversed(range(0, len(buckets))):
            if sm_value >= buckets[i]:
                outarray[i] = 1
                break

        outarray[-2] = sm_value # sum
        outarray[-1] = 1        # count
        context.write((channel, appVersion, "SIMPLE_MEASURES_" + sm_name.upper()), {path: outarray})
        
def commonCombine(values):
    out = {}
    for d in values:
        for filter_path, histogram in d.iteritems():
            existing = out.get(filter_path, None)
            if existing is None:
                out[filter_path] = histogram
                continue
            for y in range(0, len(histogram)):
                existing[y] += (histogram[y] or 0)
    return out


def combine(key, values, context):
    out = commonCombine(values)
    context.write(key, out)


def reduce(key, values, context):
    out = commonCombine(values)
    out_values = {}
    for (filter_path, histogram) in out.iteritems():
        # first, discard any malformed (non int) entries
        malformed_data = [type(_) for _ in histogram if type(_) is not int]
        if len(malformed_data):
            msg = ("discarding %s. contrained malformed type(s): %s" %
                   ('/'.join(filter_path), set(malformed_data)))
            print >> sys.stderr, msg
            return
        out_values["/".join(filter_path)] = histogram
    h_name = key[2]
    
    if h_name[0:16] == "SIMPLE_MEASURES_":
        buckets = SIMPLE_MEASURES_;
    else:
        # histogram_specs lookup below is guranteed to succeed, because of mapper
        buckets = histogram_specs.get(h_name)[1]
    final_out = {
        'buckets': buckets,
        'values': out_values
    }
    context.write("/".join(key), json.dumps(final_out))


def output(path, results):
    f = open(path, 'w')
    for k, v in results:
        f.write(k + "\t" + v + "\n")

setupjob = telemetryutils.setupjob
