# Preliminary JSON shape contracts

These Draft 2020-12 schemas describe an **unqualified credibility template** and a **proposed typed port example**. They do not implement a port router, semantic units checker, COMBINE/SBML/SED-ML conformance, biological validity, or a full production state schema.

`tools/validate_schemas.py` optionally checks the shipped two examples with the `jsonschema` library. The dependency-free reference suite does not require that library. The separate schema validation record identifies whether this optional check was actually executed during the build.

The external port's time interval, species identity, units and response model require additional semantic validation. Array shape alone does not prove increasing times or compatible dimensions. The broad reference-state write contracts should not be mistaken for implementation of these proposed ports.
