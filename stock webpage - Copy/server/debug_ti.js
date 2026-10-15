import yahooFinance from 'yahoo-finance2';
import * as ti from 'technicalindicators';
import fs from 'fs';

// I need to read computeInstitutionalFeatures from mlScreener.js manually or just copy its content.
// Since it's not exported, I can read the file and eval it, but it's simpler to export it.

// Let's modify mlScreener to export computeInstitutionalFeatures for testing.
