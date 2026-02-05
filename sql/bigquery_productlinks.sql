SELECT UPC, CIN, Products.PID, Products.PName, Products.PS_Count, Products.PS_SizeEach, Brands.BName, Brands.StoreID, Stores.SName
FROM ProductLinks

LEFT JOIN Products ON ProductLinks.PID = Products.PID
LEFT JOIN Brands ON Brands.ID = Products.BrandID
LEFT JOIN Stores ON Stores.ID = Brands.StoreID

WHERE UPC='5000246729661' OR PName="Whole Milk Drink 2 Litre" OR PS_SizeEach=2000

ORDER BY Products.PID DESC;