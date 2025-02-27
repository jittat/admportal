import sys
import json

APP_NAME_MAP = {
    'appl': 'majors',
}

input_filename = sys.argv[1]

data = json.loads(open(input_filename).read())
for item in data:
    if 'model' in item:
        model_name = item['model'].split('.')[0]
        if model_name in APP_NAME_MAP:
            new_model_name = '.'.join([APP_NAME_MAP[model_name],
                                       item['model'].split('.')[1]])
            item['model'] = new_model_name
print(json.dumps(data,indent=1))
