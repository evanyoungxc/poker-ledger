
document.addEventListener('DOMContentLoaded', () => {
    const ranks = 'AKQJT98765432'.split('');

    const ranges = {
        UTG: {pairs: '77+', suited: ['AKs','AQs','AJs','ATs','KQs','KJs','QJs','JTs','T9s'], off: ['AKo','AQo']},
        HJ:  {pairs: '66+', suited: ['A9s+','KTs+','QTs+','JTs','T9s','98s'], off: ['ATo+','KQo']},
        CO:  {pairs: '44+', suited: ['A2s+','K9s+','Q9s+','J9s+','T8s+','98s','87s','76s'], off: ['A9o+','KTo+','QJo']},
        BTN: {pairs: '22+', suited: ['A2s+','K2s+','Q7s+','J7s+','T7s+','97s+','86s+','75s+','65s','54s'], off: ['A2o+','K8o+','Q9o+','J9o+','T9o']},
        SB:  {pairs: '22+', suited: ['A2s+','K5s+','Q8s+','J8s+','T8s+','97s+','87s','76s','65s'], off: ['A2o+','K9o+','Q9o+','J9o+','T9o']}
    };

    function expand(tokens) {
        const result = new Set();
        for (const token of tokens) {
            if (!token.endsWith('+')) {
                result.add(token);
                continue;
            }
            const base = token.slice(0, -1);
            const high = base[0], low = base[1], suit = base[2];
            const highIndex = ranks.indexOf(high);
            const lowIndex = ranks.indexOf(low);
            for (let i = lowIndex; i > highIndex; i--) {
                result.add(high + ranks[i] + suit);
            }
        }
        return result;
    }

    function pairSet(minPair) {
        const low = minPair[0];
        const limit = ranks.indexOf(low);
        return new Set(ranks.slice(0, limit + 1).map(r => r + r));
    }

    function drawGrid() {
        const position = document.getElementById('position').value;
        const range = ranges[position];
        const hands = new Set([
            ...pairSet(range.pairs),
            ...expand(range.suited),
            ...expand(range.off)
        ]);
        const grid = document.getElementById('hand-grid');
        grid.replaceChildren();
        ranks.forEach((r1, i) => {
            ranks.forEach((r2, j) => {
                const hand = i === j ? r1 + r2
                    : i < j ? r1 + r2 + 's'
                    : r2 + r1 + 'o';
                const cell = document.createElement('div');
                cell.className = 'hand-cell ' + (hands.has(hand) ? 'raise' : 'fold');
                cell.textContent = hand;
                cell.title = hand + (hands.has(hand) ? ': Open raise' : ': Fold in simplified chart');
                grid.appendChild(cell);
            });
        });
    }

    document.getElementById('position').addEventListener('change', drawGrid);
    drawGrid();

document.querySelectorAll('[data-game]').forEach(button => {
        button.addEventListener('click', () => {
            const ten = button.dataset.game === 'ten';
            document.getElementById('holdem-content').hidden = ten;
            document.getElementById('ten-content').hidden = !ten;
            document.querySelectorAll('[data-game]').forEach(b =>
                b.classList.toggle('active', b === button)
            );
        });
    });
});



// Preflop equity calculator — client-side Monte Carlo simulation.
(() => {
    const RANKS = "23456789TJQKA";
    const SUITS = "shdc";
    const FULL_DECK = Array.from({length: 52}, (_, i) => i);

    const countInput = document.getElementById("player-count");
    const playersElement = document.getElementById("equity-players");
    const runButton = document.getElementById("calculate-equity");
    const resultsElement = document.getElementById("equity-results");
    const statusElement = document.getElementById("equity-status");
    const simulationInput = document.getElementById("simulation-count");

    if (!countInput || !playersElement || !runButton) return;

    const exampleHands = [
        ["As", "Ah"],
        ["Ks", "Kh"],
        ["Qs", "Qh"],
        ["Js", "Jh"],
        ["Ts", "Th"],
        ["9s", "9h"]
    ];

    function cardId(rank, suit) {
        return SUITS.indexOf(suit) * 13 + RANKS.indexOf(rank);
    }

    function displayCard(card) {
        const rank = card[0] === "T" ? "10" : card[0];
        const suit = {
            s: "♠",
            h: "♥",
            d: "♦",
            c: "♣"
        }[card[1]];
        return rank + suit;
    }

    function cardSelector(player, position, initial) {
        const select = document.createElement("select");
        select.className = "equity-card";
        select.setAttribute("aria-label",
            `Player ${player + 1}, card ${position + 1}`);

        const blank = document.createElement("option");
        blank.value = "";
        blank.textContent = "Select card";
        select.appendChild(blank);

        for (const suit of SUITS) {
            for (const rank of [...RANKS].reverse()) {
                const value = rank + suit;
                const option = document.createElement("option");
                option.value = value;
                option.textContent = displayCard(value);
                select.appendChild(option);
            }
        }

        select.value = initial;
        return select;
    }

    function currentHands() {
        return Array.from(playersElement.querySelectorAll(".equity-player"))
            .map(row =>
                Array.from(row.querySelectorAll("select"))
                    .map(select => select.value)
            );
    }

    function renderPlayers() {
        const previous = currentHands();
        const count = Number(countInput.value);
        playersElement.replaceChildren();

        for (let i = 0; i < count; i++) {
            const row = document.createElement("div");
            row.className = "equity-player";

            const title = document.createElement("strong");
            title.textContent = `Player ${i + 1}`;

            const selectors = document.createElement("div");
            selectors.className = "equity-card-pair";

            for (let j = 0; j < 2; j++) {
                const initial = previous[i]?.[j] ??
                    exampleHands[i][j];

                selectors.appendChild(
                    cardSelector(i, j, initial)
                );
            }

            row.append(title, selectors);
            playersElement.appendChild(row);
        }

        resultsElement.hidden = true;
        statusElement.textContent = "";
    }

    // Returns a comparable integer representing a five-card hand.
    // Categories: high card=0 through straight flush=8.
    function scoreFive(cards) {
        const ranks = cards.map(c => c % 13 + 2).sort((a, b) => b - a);
        const flush = cards.every(c => Math.floor(c / 13) ===
            Math.floor(cards[0] / 13));

        const counts = new Map();
        for (const rank of ranks) {
            counts.set(rank, (counts.get(rank) || 0) + 1);
        }

        const unique = [...new Set(ranks)];
        if (unique.includes(14)) unique.push(1);

        let straightHigh = 0;
        for (let i = 0; i <= unique.length - 5; i++) {
            if (unique[i] - unique[i + 4] === 4) {
                straightHigh = unique[i];
                break;
            }
        }

        const groups = [...counts.entries()]
            .map(([rank, count]) => ({rank, count}))
            .sort((a, b) => b.count - a.count || b.rank - a.rank);

        const pack = (category, kickers) =>
            [category, ...kickers, 0, 0, 0, 0, 0]
                .slice(0, 6)
                .reduce((score, value) => score * 15 + value, 0);

        if (flush && straightHigh)
            return pack(8, [straightHigh]);

        if (groups[0].count === 4)
            return pack(7, [groups[0].rank, groups[1].rank]);

        if (groups[0].count === 3 && groups[1].count === 2)
            return pack(6, [groups[0].rank, groups[1].rank]);

        if (flush)
            return pack(5, ranks);

        if (straightHigh)
            return pack(4, [straightHigh]);

        if (groups[0].count === 3)
            return pack(3, [
                groups[0].rank,
                ...groups.slice(1).map(g => g.rank).sort((a, b) => b - a)
            ]);

        if (groups[0].count === 2 && groups[1].count === 2) {
            const pairs = [groups[0].rank, groups[1].rank]
                .sort((a, b) => b - a);
            return pack(2, [...pairs, groups[2].rank]);
        }

        if (groups[0].count === 2)
            return pack(1, [
                groups[0].rank,
                ...groups.slice(1).map(g => g.rank).sort((a, b) => b - a)
            ]);

        return pack(0, ranks);
    }

    // Best five-card hand out of seven.
    function scoreSeven(cards) {
        let best = -1;

        for (let a = 0; a < 3; a++)
        for (let b = a + 1; b < 4; b++)
        for (let c = b + 1; c < 5; c++)
        for (let d = c + 1; d < 6; d++)
        for (let e = d + 1; e < 7; e++) {
            const score = scoreFive([
                cards[a], cards[b], cards[c], cards[d], cards[e]
            ]);
            if (score > best) best = score;
        }

        return best;
    }

    function validateHands(hands) {
        const cards = hands.flat();

        if (cards.some(card => !card))
            throw new Error("Select two cards for every player.");

        if (new Set(cards).size !== cards.length)
            throw new Error("A card cannot belong to multiple players.");

        return hands.map(hand =>
            hand.map(card => cardId(card[0], card[1]))
        );
    }

    function simulate(hands, trials) {
        const used = new Set(hands.flat());
        const deck = FULL_DECK.filter(card => !used.has(card));
        const wins = Array(hands.length).fill(0);
        const ties = Array(hands.length).fill(0);
        const equity = Array(hands.length).fill(0);

        for (let trial = 0; trial < trials; trial++) {
            // Partial Fisher-Yates shuffle: select five distinct board cards.
            for (let i = 0; i < 5; i++) {
                const j = i + Math.floor(Math.random() * (deck.length - i));
                [deck[i], deck[j]] = [deck[j], deck[i]];
            }

            const board = deck.slice(0, 5);
            const scores = hands.map(hand =>
                scoreSeven([...hand, ...board])
            );

            const best = Math.max(...scores);
            const winners = scores
                .map((score, index) => score === best ? index : -1)
                .filter(index => index !== -1);

            for (const index of winners) {
                equity[index] += 1 / winners.length;
                if (winners.length === 1) wins[index]++;
                else ties[index]++;
            }
        }

        return {wins, ties, equity};
    }

    function renderResults(hands, data, trials) {
        resultsElement.replaceChildren();

        const heading = document.createElement("h3");
        heading.textContent = "Preflop Equity Results";
        resultsElement.appendChild(heading);

        hands.forEach((hand, i) => {
            const equity = 100 * data.equity[i] / trials;
            const win = 100 * data.wins[i] / trials;
            const tie = 100 * data.ties[i] / trials;

            const card = document.createElement("div");
            card.className = "equity-result";

            const top = document.createElement("div");
            top.className = "equity-result-top";

            const name = document.createElement("strong");
            name.textContent = `Player ${i + 1} — ${hand.map(displayCard).join(" ")}`;

            const percent = document.createElement("strong");
            percent.textContent = equity.toFixed(1) + "%";

            top.append(name, percent);

            const track = document.createElement("div");
            track.className = "equity-bar";

            const fill = document.createElement("div");
            fill.style.width = equity + "%";
            track.appendChild(fill);

            const detail = document.createElement("small");
            detail.textContent =
                `Win: ${win.toFixed(1)}% · Tie: ${tie.toFixed(1)}%`;

            card.append(top, track, detail);
            resultsElement.appendChild(card);
        });

        resultsElement.hidden = false;
    }

    countInput.addEventListener("change", renderPlayers);

    playersElement.addEventListener("change", () => {
        resultsElement.hidden = true;
        statusElement.textContent = "";
    });

    runButton.addEventListener("click", () => {
        try {
            const hands = currentHands();
            const parsed = validateHands(hands);
            const trials = Number(simulationInput.value);

            runButton.disabled = true;
            statusElement.textContent = `Simulating ${trials.toLocaleString()} boards...`;
            resultsElement.hidden = true;

            // Let the browser paint the status before the calculation.
            setTimeout(() => {
                try {
                    const result = simulate(parsed, trials);
                    renderResults(hands, result, trials);
                    statusElement.textContent =
                        `Completed ${trials.toLocaleString()} simulations.`;
                } catch (error) {
                    statusElement.textContent = error.message;
                } finally {
                    runButton.disabled = false;
                }
            }, 30);
        } catch (error) {
            statusElement.textContent = error.message;
            resultsElement.hidden = true;
        }
    });

    renderPlayers();
})();
