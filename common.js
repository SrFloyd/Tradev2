const TP = {
  coins:[{s:'BTC',n:'Bitcoin'},{s:'ETH',n:'Ethereum'},{s:'SOL',n:'Solana'},{s:'BNB',n:'BNB'},{s:'XRP',n:'XRP'},{s:'ADA',n:'Cardano'},{s:'DOGE',n:'Dogecoin'},{s:'AVAX',n:'Avalanche'},{s:'LINK',n:'Chainlink'},{s:'DOT',n:'Polkadot'},{s:'MATIC',n:'Polygon'},{s:'LTC',n:'Litecoin'}],
  get coin(){const saved=localStorage.getItem('tp.coin.symbol');if(saved)return saved;const idx=+(localStorage.getItem('tp.coin')||0);return this.coins[Math.max(0,Math.min(this.coins.length-1,idx))].s},
  set coin(v){localStorage.setItem('tp.coin.symbol',v);const idx=this.coins.findIndex(c=>c.s===v);if(idx>=0)localStorage.setItem('tp.coin',String(idx))},
  get tf(){return localStorage.getItem('tp.tf.shared')||'15m'},set tf(v){localStorage.setItem('tp.tf.shared',v)},
  money(v){if(!Number.isFinite(Number(v)))return '—';return 'US$ '+Number(v).toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2})},
  num(v,d=6){return Number(v).toLocaleString('pt-BR',{maximumFractionDigits:d})},
  read(k,f=[]){try{const x=JSON.parse(localStorage.getItem(k)||'null');return x==null?f:x}catch{return f}},
  save(k,v){try{localStorage.setItem(k,JSON.stringify(v))}catch(e){console.warn(e)}},
  escape(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))},
  async price(symbol=this.coin){const pair=symbol.endsWith('USDT')?symbol:symbol+'USDT';const r=await fetch('https://data-api.binance.vision/api/v3/ticker/price?symbol='+encodeURIComponent(pair));if(!r.ok)throw Error('API de mercado indisponível');return +(await r.json()).price},
  async ticker(symbol=this.coin){const pair=symbol.endsWith('USDT')?symbol:symbol+'USDT';const r=await fetch('https://data-api.binance.vision/api/v3/ticker/24hr?symbol='+encodeURIComponent(pair));if(!r.ok)throw Error('API de mercado indisponível');return await r.json()},
  async klines(symbol=this.coin, interval=this.tf, limit=500){const pair=symbol.endsWith('USDT')?symbol:symbol+'USDT';const r=await fetch(`https://data-api.binance.vision/api/v3/klines?symbol=${encodeURIComponent(pair)}&interval=${encodeURIComponent(interval)}&limit=${Math.min(1000,limit)}`);if(!r.ok)throw Error('Não foi possível carregar o histórico público da Binance');return (await r.json()).map(k=>({time:+k[0],open:+k[1],high:+k[2],low:+k[3],close:+k[4],volume:+k[5]}))},
  select(id){const el=document.getElementById(id);el.innerHTML=this.coins.map(c=>`<option value="${c.s}" ${c.s===this.coin?'selected':''}>${c.n} (${c.s.replace('USDT','')})</option>`).join('');el.addEventListener('change',()=>{this.coin=el.value;document.dispatchEvent(new CustomEvent('tp-coin-change',{detail:el.value}))})},
  nav(){const current=location.pathname.split('/').pop()||'dashboard.html';document.querySelectorAll('.nav a').forEach(a=>{if(a.getAttribute('href')===current)a.classList.add('active')})},
  init(){this.nav();document.querySelectorAll('[data-coin-select]').forEach(e=>this.select(e.id));document.querySelectorAll('[data-tf-select]').forEach(e=>{e.value=this.tf;e.addEventListener('change',()=>this.tf=e.value)})}
};
TP.init();
