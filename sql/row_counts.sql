SELECT table_name AS "Table",
table_schema AS "Schema",
       FORMAT(TABLE_ROWS, "N0") AS "N_Rows",
       CURRENT_TIMESTAMP AS TimeNow
FROM information_schema.tables
WHERE table_schema IN ("pricedb", "pricedb2")
GROUP BY table_name, table_schema
ORDER BY TABLE_ROWS DESC;