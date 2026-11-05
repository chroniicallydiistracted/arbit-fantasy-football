import { readFileSync } from 'node:fs';
import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
for (const [schemaPath, examplePath] of [
  ['packages/contracts/schemas/league-config.schema.json', 'config/league.json'],
  ['packages/contracts/schemas/recommendation.schema.json', 'tests/fixtures/recommendation.example.json'],
  ['packages/contracts/schemas/play-script.schema.json', 'tests/fixtures/live/play-script.example.json'],
  ['packages/contracts/schemas/play-script.schema.json', 'tests/fixtures/live/play-script.punt.example.json'],
  ['packages/contracts/schemas/play-board.schema.json', 'tests/fixtures/live/play-board.example.json'],
]) {
  const validate = ajv.compile(JSON.parse(readFileSync(schemaPath, 'utf8')));
  if (!validate(JSON.parse(readFileSync(examplePath, 'utf8')))) {
    console.error(ajv.errorsText(validate.errors));
    process.exitCode = 1;
  } else console.log(`PASS: ${examplePath}`);
}
