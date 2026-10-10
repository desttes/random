# Winter tire watch
Checks Craigslist Boston every 4h for 15" winter tires (Prius 2010, 195/65R15) and emails/texts new listings.
Setup: add repo secrets (Settings > Secrets > Actions): `SMTP_USER`, `SMTP_PASS` (Gmail app password), `EMAIL_TO`;
optional SMS via Twilio: `TWILIO_SID`, `TWILIO_TOKEN`, `TWILIO_FROM`, `SMS_TO`. Merge to the default branch
(scheduled workflows only run there), then run once via Actions > Run workflow.
