#!/usr/bin/env python3
"""Optional shape-only check. Requires jsonschema; not used by the core test suite."""
from pathlib import Path
import importlib.metadata,json,sys
R=Path(__file__).resolve().parents[1]
try:
    from jsonschema import Draft202012Validator
except ImportError:
    raise SystemExit("Optional check requires jsonschema; reference tests do not depend on it.")
records=[]
for schema_name,instance_name in [('credibility_case.schema.json','credibility_case.template.json'),
                                ('external_port.schema.json','external_port.example.json')]:
    schema=json.loads((R/'schemas'/schema_name).read_text())
    value=json.loads((R/'configs'/instance_name).read_text())
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(value)
    records.append({'schema':schema_name,'instance':instance_name,'outcome':'pass'})
print(json.dumps({'scope':'shape only, no biological or runtime semantics',
                  'jsonschema_version':importlib.metadata.version('jsonschema'),'records':records},indent=2))
