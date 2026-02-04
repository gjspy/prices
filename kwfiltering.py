#from copy import deepcopy

with open("state/keywords.csv","r") as f:
	file = f.read()

data = file.split(",")

with open("state/keywords2.csv","r") as f:
	file = f.read()

new_data = file.split(",")
print(data)
print(new_data)

with open("state/rejects.csv","r") as f:
	file = f.read()

rejects = file.split(",")




while True:
	x = [v for v in data if not v in new_data and not v in rejects]

	v = x[0]
	words = v.split(" ")
	print(f"NEXT {len(x)}")

	deleted_this = False

	for vv in x:
		if (v == vv): continue
		if (deleted_this): break
		words2 = vv.split(" ")

		for word in words2:
			if (not word in words): continue

			user = input(f"1 to delete 1, 2 to delete 2, nothing to ignore:    1: _{v}_  2: _{vv}_ ")

			if (user == "1"):	
				rejects.append(v)
				#new_data.append(vv)
				deleted_this = True

			elif (user == "2"):
				#new_data.append(v)
				rejects.append(vv)
			
			#with open("state/keywords2.csv","w") as f:
			#	f.write(",".join(new_data))

			with open("state/rejects.csv","a") as f:
				f.write(",".join(rejects))

			
			break
	
	if (deleted_this): continue
	user = input(f"accept this? _{v}_, 1 to accept, nothing to delete ")

	if (user == "1"): new_data.append(v)
	else: rejects.append(v)

	with open("state/keywords2.csv","w") as f:
		f.write(",".join(new_data))

	with open("state/rejects.csv","w") as f:
		f.write(",".join(rejects))



for i, v in enumerate(x):
	user = input(f"{len(x) - i} press enter to keep, anything to reject:    _{v}_ ")

	if (user == ""):	
		new_data.append(v)

		with open("state/keywords2.csv","w") as f:
			f.write(",".join(new_data))
	
	else:
		rejects.append(v)

		with open("state/rejects.csv","w") as f:
			f.write(",".join(rejects))