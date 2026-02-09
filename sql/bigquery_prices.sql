SELECT * FROM Prices

JOIN Products ON Products.PID=Prices.PID
JOIN Brands ON Products.BrandID=Brands.ID

ORDER BY Products.PID;