# ChatGPT Summarize All Missions

Takes a file of mission recommendations, creates a pivot on the field, and uses ChatGPT to summarize all recommendations into a season rec.

## File format

|field_id|field_name|client_name|farm_name|crop_name|area|pass_number|order_date|org_name|org_id|order_id|suggestion_created|ag_assistant|mission_rec|cycle_id|
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
|1274316|Racetrack R|Grower name|farm|Soybean|14.20|1|2025-07-02|org|1234|223443|2025-07-12|We've identified issues in plant emergence, and with weeds pressure.|

## Usage
1. Create `.env` file as:
```
OPENAI_API_KEY="KEY"
```

2. Then run the script:
```
$ python summarize.py --input data/missions.csv
```
 Produces `data/missions-summarized.csv`.