const kwrds = ["cheese", "bread", "milk", "water", "soda", "fruit", "veg", "crisps", "snacks", "pastry"];
let todo = [];

const timePerChar = 150;
const timeEach = Math.max(...kwrds.map(v => v.length)) * timePerChar;
const extraDelay = 5000;

const label = document.querySelector("#nav-bar-search-bar label[for='search']");

setInterval(() => {
	if (todo.length == 0) todo = structuredClone(kwrds);

	const i = Math.floor(Math.random() * todo.length);
	const choice = todo[i];
	todo.splice(i, 1);


	const l = choice.length;
	const delay = timeEach + extraDelay - (l * timePerChar);
	

	for (let i = 0; i <= l; i++) {
		setTimeout(() => {
			label.textContent = `Search for ${choice.slice(0, i)}...`;
		}, i * timePerChar);
	};

	for (let i = 0; i <= l; i++) {
		setTimeout(() => {
			label.textContent = `Search for ${choice.slice(0, (l - i))}...`;
		}, (l * timePerChar) + delay + (i * timePerChar));
	};

	
	console.log(choice);
}, (timeEach * 2) + extraDelay);