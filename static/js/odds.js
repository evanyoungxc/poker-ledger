
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

    function drawOuts() {
        const outs = Number(document.getElementById('outs').value);
        document.getElementById('outs-label').textContent = outs;
        document.getElementById('one-card').textContent = (100 * outs / 47).toFixed(1) + '%';
        const missBoth = ((47 - outs) / 47) * ((46 - outs) / 46);
        document.getElementById('two-cards').textContent = (100 * (1 - missBoth)).toFixed(1) + '%';
    }

    document.getElementById('outs').addEventListener('input', drawOuts);
    drawOuts();

    function drawPotOdds() {
        const pot = Math.max(0, Number(document.getElementById('pot').value) || 0);
        const call = Math.max(0, Number(document.getElementById('call').value) || 0);
        const equity = Math.min(100, Math.max(0, Number(document.getElementById('equity').value) || 0)) / 100;
        const total = pot + 2 * call;
        const needed = total ? 100 * call / total : 0;
        const ev = equity * (pot + call) - (1 - equity) * call;
        document.getElementById('required-equity').textContent = needed.toFixed(1) + '%';
        document.getElementById('call-ev').textContent =
            (ev >= 0 ? '+' : '-') + '$' + Math.abs(ev).toFixed(2);
    }

    ['pot', 'call', 'equity'].forEach(id =>
        document.getElementById(id).addEventListener('input', drawPotOdds)
    );
    drawPotOdds();

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
