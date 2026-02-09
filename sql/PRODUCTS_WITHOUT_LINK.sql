SELECT Products.*
FROM Products
LEFT JOIN ProductLinks
  ON Products.PID = ProductLinks.PID
WHERE ProductLinks.ID IS NULL;