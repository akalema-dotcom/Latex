const agents = ["ATLAS","NOVA","ARIA","STOCK","MERCURY","LEDGER","INSIGHT","PULSE","ORBIT","SENTINEL"];

export default function Home() {
  return (
    <main style={{maxWidth:1180,margin:"0 auto",padding:"72px 24px"}}>
      <p style={{letterSpacing:2,opacity:.6}}>AI BUSINESS WORKFORCE</p>
      <h1 style={{fontSize:"clamp(42px,7vw,78px)",lineHeight:1.02,maxWidth:850}}>Your business, powered by an AI workforce.</h1>
      <p style={{fontSize:20,lineHeight:1.6,opacity:.75,maxWidth:720}}>One platform for sales, customers, inventory, procurement, finance and reporting.</p>
      <section style={{marginTop:60,display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(210px,1fr))",gap:16}}>
        {agents.map(name => <article key={name} style={{padding:22,border:"1px solid rgba(255,255,255,.12)",borderRadius:18,background:"rgba(255,255,255,.04)"}}><strong>{name}</strong><p style={{opacity:.65}}>Agent foundation ready.</p></article>)}
      </section>
    </main>
  );
}
