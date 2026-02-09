SELECT table_name AS "Table",
       FORMAT(TABLE_ROWS, "N0") AS "N_Rows"
FROM information_schema.tables
WHERE table_schema="pricedb"
GROUP BY table_name
ORDER BY "N_Rows" DESC;