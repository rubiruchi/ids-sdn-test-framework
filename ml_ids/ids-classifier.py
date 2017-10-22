import os
import pandas as pd
import json
import glob
import gc
import numpy as np
from datetime import datetime
from collections import defaultdict
from sklearn import ensemble
from sklearn.metrics import accuracy_score
from sklearn.externals import joblib
from sklearn.model_selection import train_test_split

DATA_PATH = os.path.join('../data', 'IDS2012')


def load_data_set(data_path):
    json_path = os.path.join(data_path, '*.json')
    dataset = []
    for file in glob.glob(json_path):
        filename = file.split('/')[-1].split('.')[0]
        json_file = None
        temp = None
        try:
            json_file = open(file, 'r')
            temp = json.load(json_file).get('dataroot').get(filename)

            # Clean dataset
            for item in temp:
                # Delete unnecessary features
                del item['appName']
                del item['sourcePayloadAsBase64']
                del item['sourcePayloadAsUTF']
                del item['destinationPayloadAsBase64']
                del item['destinationPayloadAsUTF']
                del item['sourceTCPFlagsDescription']
                del item['destinationTCPFlagsDescription']

                # Count total number of IP address occurences
                ip_counts['source'][item['source']] += 1
                ip_counts['destination'][item['destination']] += 1

                # Convert into more appropriate features
                item['direction'] = convert_direction(item['direction'])
                item['duration'] = calculate_duration(
                    item.pop('startDateTime'), item.pop('stopDateTime'))
                item['Tag'] = convert_class(item['Tag'])

                # Delete features for prototype
                del item['totalSourceBytes']
                del item['totalDestinationBytes']
                del item['totalDestinationPackets']
                del item['totalSourcePackets']
                del item['direction']
                del item['duration']

            dataset += temp
        finally:
            if json_file is not None:
                json_file.close()
                json_file = None
                gc.collect()
    return dataset


def convert_class(x):
    return int(x != 'Normal')


def convert_direction(x):
    return int(x != 'L2R')


def calculate_duration(start, stop):
    dt = datetime.strptime(stop, '%Y-%m-%dT%H:%M:%S') - datetime.strptime(
        start, '%Y-%m-%dT%H:%M:%S')
    return dt.total_seconds()


# Load training data
ip_counts = {'source': defaultdict(int), 'destination': defaultdict(int)}
flows = load_data_set(DATA_PATH)

for flow in flows:
    flow['source_ip_count'] = ip_counts['source'][flow.pop('source')]
    flow['destination_ip_count'] = ip_counts['destination'][flow.pop(
        'destination')]

temp = pd.DataFrame.from_dict(flows)
data = pd.get_dummies(temp, prefix=['protocol'], columns=['protocolName'])
del data['sensorInterfaceId']
del data['startTime']
print data

y = data['Tag'].values
del data['Tag']
X_train, X_test, y_train, y_test = train_test_split(
    data, y, stratify=y, test_size=0.2)

# Train classifier
clf = ensemble.AdaBoostClassifier()
clf.fit(X_train, y_train)

# Test classifier
pred = clf.predict(X_test)
unique, counts = np.unique(pred, return_counts=True)
print dict(zip(unique, counts))

# Check accuracy
accuracy = accuracy_score(y_test, pred)
print 'Accuracy:', accuracy

# Save model
joblib.dump(clf, 'adaboost-ids.pkl')