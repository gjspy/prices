SELECT TABLE_NAME AS "Table",
       ROUND(SUM(DATA_LENGTH + INDEX_LENGTH) / 1024 / 1024, 2) AS "Size_MB",
       FORMAT(TABLE_ROWS, "N0") AS "N_Rows"
FROM information_schema.tables
WHERE table_schema="pricedb"
GROUP BY TABLE_NAME
ORDER BY "N_Rows" DESC;