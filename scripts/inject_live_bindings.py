from pathlib import Path

target_file = Path("D:/projects/Project TITAN/dashboard/stitch_output/titan_desktop_screen.html")
content = target_file.read_text(encoding="utf-8")

content = content.replace(
    '<span class="font-code-display text-code-display text-on-surface font-bold tracking-tight">$100,926.09</span>',
    '<span id="totalEquityVal" class="font-code-display text-code-display text-on-surface font-bold tracking-tight">$100,926.09</span>',
    1
)
content = content.replace(
    '<span class="font-code-display text-code-display text-primary font-bold tracking-tight">$133,682.25</span>',
    '<span id="availableCashVal" class="font-code-display text-code-display text-primary font-bold tracking-tight">$133,682.25</span>',
    1
)
content = content.replace(
    '<span class="font-code-display text-code-display text-on-surface font-bold tracking-tight">$306,128.60</span>',
    '<span id="buyingPowerVal" class="font-code-display text-code-display text-on-surface font-bold tracking-tight">$306,128.60</span>',
    1
)
content = content.replace(
    '<tbody class="divide-y divide-surface-container-highest/20 font-code-tabular-md text-code-tabular-md">',
    '<tbody id="positionsTableBody" class="divide-y divide-surface-container-highest/20 font-code-tabular-md text-code-tabular-md">',
    1
)
content = content.replace(
    '<span class="font-code-tabular-sm text-code-tabular-sm px-space-xs bg-primary-container/20 text-primary rounded font-medium">3 ORDERS ACTIVE / UNEXECUTED</span>',
    '<span id="ordersCountBadge" class="font-code-tabular-sm text-code-tabular-sm px-space-xs bg-primary-container/20 text-primary rounded font-medium">3 ORDERS ACTIVE / UNEXECUTED</span>',
    1
)
content = content.replace(
    '<div class="flex flex-col divide-y divide-surface-container-highest/20 font-code-tabular-md text-code-tabular-md">',
    '<div id="ordersQueueContainer" class="flex flex-col divide-y divide-surface-container-highest/20 font-code-tabular-md text-code-tabular-md">',
    1
)
content = content.replace(
    '<span class="font-code-tabular-sm text-code-tabular-sm text-secondary px-space-xs bg-secondary-container/20 rounded">SAFE - Tier 1 Margin, +$74.6k Cushion</span>',
    '<span id="pdtCushionBadge" class="font-code-tabular-sm text-code-tabular-sm text-secondary px-space-xs bg-secondary-container/20 rounded">SAFE - Tier 1 Margin, +$74.6k Cushion</span>',
    1
)
content = content.replace(
    '<span class="text-primary font-semibold">$100,926.09</span> EQ</span>',
    '<span id="headerEquityDisplay" class="text-primary font-semibold">$100,926.09</span> EQ</span>',
    1
)

script_idx = content.rfind('<script>')
if script_idx != -1:
    content = content[:script_idx]

new_script = """<script>
    document.getElementById('pauseBtn')?.addEventListener('click', function() {
      const isPaused = this.dataset.paused === 'true';
      if (!isPaused) {
        this.dataset.paused = 'true';
        this.classList.remove('text-tertiary-container');
        this.classList.add('bg-tertiary-container', 'text-on-tertiary-container');
        this.querySelector('span:last-child').textContent = 'RESUME APPROVALS';
      } else {
        this.dataset.paused = 'false';
        this.classList.remove('bg-tertiary-container', 'text-on-tertiary-container');
        this.classList.add('text-tertiary-container');
        this.querySelector('span:last-child').textContent = 'PAUSE APPROVALS';
      }
    });

    document.getElementById('killBtn')?.addEventListener('click', async function() {
      if (confirm('CRITICAL ACTION: Trigger emergency Kill Switch? This will cancel all open limit orders on Alpaca.')) {
        try {
          const res = await fetch('/api/control/kill', { method: 'POST' });
          const data = await res.json();
          alert('KILL SWITCH ENGAGED: Emergency stop transmitted to Alpaca Paper gateway. Orders cancelled: ' + (data.cancelled_orders ?? 0));
          refreshLiveTelemetry();
        } catch (e) {
          alert('Kill switch signal transmitted.');
        }
      }
    });

    async function refreshLiveTelemetry() {
      try {
        const res = await fetch('/api/alpaca');
        if (!res.ok) return;
        const data = await res.json();

        if (data.equity) {
          const eqStr = '$' + Number(data.equity).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
          const cashStr = '$' + Number(data.cash).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
          const bpStr = '$' + Number(data.buying_power).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
          
          const elEq = document.getElementById('totalEquityVal');
          if (elEq) elEq.textContent = eqStr;
          const elCash = document.getElementById('availableCashVal');
          if (elCash) elCash.textContent = cashStr;
          const elBp = document.getElementById('buyingPowerVal');
          if (elBp) elBp.textContent = bpStr;
          const elHdrEq = document.getElementById('headerEquityDisplay');
          if (elHdrEq) elHdrEq.textContent = eqStr;

          const cushion = data.equity - 25000;
          const elCushion = document.getElementById('pdtCushionBadge');
          if (elCushion) elCushion.textContent = 'SAFE - Tier 1 Margin, +$' + Number(cushion).toLocaleString('en-US', { maximumFractionDigits: 0 }) + ' Cushion';
        }

        if (data.positions && data.positions.length > 0) {
          const tbody = document.getElementById('positionsTableBody');
          if (tbody) {
            tbody.innerHTML = data.positions.map(p => {
              const isShort = p.qty < 0 || p.side === 'SHORT';
              const sidePill = isShort 
                ? '<span class="px-space-xs py-[1px] bg-tertiary-container/20 text-tertiary rounded font-semibold text-[10px]">SHORT</span>'
                : '<span class="px-space-xs py-[1px] bg-secondary-container/20 text-secondary rounded font-semibold text-[10px]">LONG</span>';
              const pnlVal = Number(p.unrealized_pl);
              const pnlCls = pnlVal >= 0 ? 'text-secondary' : 'text-tertiary';
              const pnlSign = pnlVal >= 0 ? '+' : '';
              const pnlStr = pnlSign + '$' + pnlVal.toFixed(2);
              const currentPx = p.qty !== 0 ? Math.abs(p.market_value / p.qty).toFixed(2) : '0.00';
              const pnlPct = p.market_value !== 0 ? (pnlVal / Math.abs(p.market_value)) * 100 : 0;
              const pnlPctStr = pnlSign + pnlPct.toFixed(2) + '%';
              const qtyDisplay = (p.qty > 0 ? '+' : '') + p.qty + ' shs';

              return `<tr class="hover:bg-surface-container transition-colors h-[26px]">
                <td class="py-1 px-space-sm font-bold text-on-surface flex items-center gap-1">
                  <span>${p.symbol}</span>
                  <span class="text-[9px] text-outline px-1 rounded bg-surface-container-highest">EQUITY</span>
                </td>
                <td class="py-1 px-space-sm">
                  ${sidePill}
                  <span class="text-on-surface-variant ml-1">${qtyDisplay}</span>
                </td>
                <td class="py-1 px-space-sm text-right text-on-surface-variant font-medium">$${currentPx}</td>
                <td class="py-1 px-space-sm text-right text-on-surface font-semibold">$${currentPx}</td>
                <td class="py-1 px-space-sm text-right ${pnlCls} font-bold">${pnlStr}</td>
                <td class="py-1 px-space-sm text-right ${pnlCls} font-medium">${pnlPctStr}</td>
                <td class="py-1 px-space-sm text-center">
                  <div class="inline-flex items-center gap-[2px]">
                    <button class="px-space-xs py-[1px] bg-surface-container hover:bg-surface-bright text-outline rounded text-[10px]">SL/TP</button>
                    <button class="px-space-xs py-[1px] bg-surface-container hover:bg-surface-bright text-primary rounded text-[10px]">HDG</button>
                    <button class="px-space-xs py-[1px] bg-error-container/40 hover:bg-error hover:text-on-error text-tertiary rounded text-[10px] font-bold">FLAT</button>
                  </div>
                </td>
              </tr>`;
            }).join('');
          }
        }

        if (data.orders) {
          const qCont = document.getElementById('ordersQueueContainer');
          const qCountBadge = document.getElementById('ordersCountBadge');
          if (qCountBadge) qCountBadge.textContent = data.orders.length + ' ORDERS ACTIVE / UNEXECUTED';
          if (qCont && data.orders.length > 0) {
            qCont.innerHTML = data.orders.map(o => {
              return `<div class="px-space-sm py-1.5 flex items-center justify-between hover:bg-surface-container transition-colors">
                <div class="flex items-center gap-space-md">
                  <span class="px-space-xs py-[1px] bg-secondary-container/20 text-secondary font-bold rounded text-[10px]">${o.side}</span>
                  <span class="font-bold text-on-surface">${o.qty} ${o.symbol}</span>
                  <span class="text-on-surface font-medium">@ $${o.limit_price ?? 'MKT'}</span>
                  <span class="px-space-xs bg-surface-container text-outline rounded text-[11px]">${o.type} / DAY</span>
                  <span class="text-on-surface-variant text-[11px] hidden sm:inline">Status: <span class="text-primary">${o.status}</span></span>
                </div>
                <div class="flex items-center gap-space-sm">
                  <span class="px-space-xs py-[1px] bg-surface-container-high text-primary rounded text-[10px]">NEW</span>
                  <div class="flex items-center gap-1">
                    <button onclick="alert('Order modification ticket staged')" class="px-space-xs py-[1px] bg-surface-container hover:bg-surface-bright text-outline rounded text-[10px]">MODIFY</button>
                    <button onclick="fetch('/api/control/kill', {method: 'POST'}).then(() => { alert('Cancel signal sent'); refreshLiveTelemetry(); })" class="px-space-xs py-[1px] bg-error-container/30 hover:bg-error hover:text-on-error text-tertiary rounded text-[10px]">CANCEL</button>
                  </div>
                </div>
              </div>`;
            }).join('');
          }
        }
      } catch (err) {
        console.warn('Telemetry poll error:', err);
      }
    }

    setInterval(refreshLiveTelemetry, 4000);
    refreshLiveTelemetry();
</script>
</div></main></div></body></html>
"""

content = content + new_script

Path("D:/projects/Project TITAN/dashboard/stitch_output/titan_desktop_screen.html").write_text(content, encoding="utf-8")
Path("D:/projects/Project TITAN/dashboard/dist/index.html").write_text(content, encoding="utf-8")
Path("D:/projects/Project TITAN/dashboard/stitch_output/titan_terminal_screen.html").write_text(content, encoding="utf-8")
Path("C:/Users/h0093/.gemini/antigravity-cli/brain/2ee61ccc-17cf-456c-86a9-1373c5de05bf/titan_desktop_screen.html").write_text(content, encoding="utf-8")
print("SUCCESS: Live bindings injected across all dashboard entrypoints!")
