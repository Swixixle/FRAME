import { buildWikidataReceipt } from '../packages/sources/index.js';

const result = await buildWikidataReceipt('Tucker Carlson');
console.log(JSON.stringify(result.narrative, null, 2));
