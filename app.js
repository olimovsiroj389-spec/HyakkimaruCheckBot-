(() => {
  const tg = window.Telegram?.WebApp;
  tg?.ready();
  tg?.expand();

  const questions = [
    { q: "Muammoga duch kelsangiz, birinchi qiladigan ishingiz?", a: [
      ["Darhol jasorat bilan qarshi chiqaman.", "gryffindor"],
      ["Eng foydali strategiyani tuzaman.", "slytherin"],
      ["Avval barcha ma'lumotni tahlil qilaman.", "ravenclaw"],
      ["Boshqalarning fikrini ham eshitaman.", "hufflepuff"]
    ]},
    { q: "Do'stlaringiz sizni ko'proq qanday ta'riflaydi?", a: [
      ["Dadilligi bilan", "gryffindor"],
      ["Maqsadga intiluvchanligi bilan", "slytherin"],
      ["Aqlliligi bilan", "ravenclaw"],
      ["Sadoqati bilan", "hufflepuff"]
    ]},
    { q: "Sizga qaysi mashg'ulot qiziqroq?", a: [
      ["Sarguzasht va yangi tajriba", "gryffindor"],
      ["Musobaqa va g'alaba", "slytherin"],
      ["Kitob, jumboq va kashfiyot", "ravenclaw"],
      ["Do'stlar bilan foydali loyiha", "hufflepuff"]
    ]},
    { q: "Qaysi qadriyat siz uchun eng muhim?", a: [
      ["Jasorat", "gryffindor"],
      ["Ambitsiya", "slytherin"],
      ["Bilim", "ravenclaw"],
      ["Halollik", "hufflepuff"]
    ]},
    { q: "Yangi guruhga kirdingiz. Siz...", a: [
      ["Birinchi bo'lib tashabbus ko'rsataman.", "gryffindor"],
      ["Kim nima qila olishini tezda baholayman.", "slytherin"],
      ["Avval kuzatib, keyin gapiraman.", "ravenclaw"],
      ["Hamma bilan til topishishga harakat qilaman.", "hufflepuff"]
    ]},
    { q: "Qiyin tanlov oldida sizga nima yordam beradi?", a: [
      ["Ichki jur'at", "gryffindor"],
      ["Uzoq muddatli foyda", "slytherin"],
      ["Mantiq", "ravenclaw"],
      ["Vijdon", "hufflepuff"]
    ]},
    { q: "Sizningcha yaxshi yetakchi qanday bo'ladi?", a: [
      ["Odamlarga namuna bo'ladi", "gryffindor"],
      ["Maqsadni aniq qo'yadi", "slytherin"],
      ["To'g'ri qaror qabul qiladi", "ravenclaw"],
      ["Jamoasini qo'llab-quvvatlaydi", "hufflepuff"]
    ]},
    { q: "Biror sirni bilib qoldingiz...", a: [
      ["Kerak bo'lsa himoya qilaman.", "gryffindor"],
      ["Vaziyatni foydali tomonga buraman.", "slytherin"],
      ["Nega bunday bo'lganini tushunishga harakat qilaman.", "ravenclaw"],
      ["Ishonchni buzmayman.", "hufflepuff"]
    ]},
    { q: "Qaysi xususiyatni o'zingizda kuchaytirishni xohlardingiz?", a: [
      ["Qo'rqmaslik", "gryffindor"],
      ["Qat'iyat", "slytherin"],
      ["Ijodkorlik", "ravenclaw"],
      ["Sabr", "hufflepuff"]
    ]},
    { q: "Yutqazib qo'ydingiz. Keyingi qadam?", a: [
      ["Qayta urinib ko'raman.", "gryffindor"],
      ["Xatoni tuzatib, boshqa yo'l topaman.", "slytherin"],
      ["Nima noto'g'ri bo'lganini tahlil qilaman.", "ravenclaw"],
      ["Tajriba qilib, sabr bilan davom etaman.", "hufflepuff"]
    ]},
    { q: "Qaysi so'z sizga ko'proq yoqadi?", a: [
      ["Jasorat", "gryffindor"],
      ["G'alaba", "slytherin"],
      ["Bilim", "ravenclaw"],
      ["Sadoqat", "hufflepuff"]
    ]},
    { q: "Oxirida sizni qaysi gap ifodalaydi?", a: [
      ["Qo'rquv bo'lsa ham oldinga yuraman.", "gryffindor"],
      ["Maqsadimni topib, unga yetaman.", "slytherin"],
      ["Har doim yangi narsani o'rganaman.", "ravenclaw"],
      ["Yaqinlarimni tashlab ketmayman.", "hufflepuff"]
    ]}
  ];

  const facultyInfo = {
    gryffindor: {name:"Gryffindor", emoji:"🦁", title:"Jasorat va qat'iyat", text:"Siz jasorat, dadillik va do'stlar uchun turish kabi fazilatlarni qadrlaysiz."},
    slytherin: {name:"Slytherin", emoji:"🐍", title:"Maqsad va topqirlik", text:"Siz maqsad sari intiluvchan, topqir va strategik fikrlashni yaxshi ko'rasiz."},
    ravenclaw: {name:"Ravenclaw", emoji:"🦅", title:"Aql va ijod", text:"Siz bilim, qiziquvchanlik va noodatiy fikrlashni qadrlaysiz."},
    hufflepuff: {name:"Hufflepuff", emoji:"🦡", title:"Sadoqat va mehr", text:"Siz halollik, sabr, sadoqat va boshqalarga yordam berishni qadrlaysiz."}
  };

  let index = 0;
  let scores = {gryffindor:0,slytherin:0,ravenclaw:0,hufflepuff:0};
  let selectedFaculty = "gryffindor";

  const $ = (id) => document.getElementById(id);
  const screens = ["intro","quiz","thinking","result"];
  function show(name){ screens.forEach(s => $(s).classList.toggle("active", s === name)); window.scrollTo(0,0); }

  $("startBtn").addEventListener("click", () => { index=0; scores={gryffindor:0,slytherin:0,ravenclaw:0,hufflepuff:0}; render(); show("quiz"); });
  $("againBtn").addEventListener("click", () => { index=0; scores={gryffindor:0,slytherin:0,ravenclaw:0,hufflepuff:0}; render(); show("quiz"); });

  function render(){
    const item=questions[index];
    $("progressText").textContent=`${index+1} / ${questions.length}`;
    $("progressFill").style.width=`${((index)/questions.length)*100}%`;
    $("questionText").textContent=item.q;
    const wrap=$("options"); wrap.innerHTML="";
    item.a.forEach(([text,faculty])=>{
      const b=document.createElement("button"); b.className="option"; b.textContent=text;
      b.addEventListener("click",()=>answer(faculty)); wrap.appendChild(b);
    });
  }

  function answer(faculty){
    scores[faculty]+=1;
    if(index < questions.length-1){ index+=1; render(); }
    else finish();
  }

  function finish(){
    show("thinking");
    setTimeout(()=>{
      const order=["gryffindor","slytherin","ravenclaw","hufflepuff"];
      selectedFaculty=order.sort((a,b)=>scores[b]-scores[a])[0];
      const f=facultyInfo[selectedFaculty];
      $("resultEmoji").textContent=f.emoji; $("resultName").textContent=f.name; $("resultTitle").textContent=f.title; $("resultText").textContent=f.text;
      $("progressFill").style.width="100%";
      const box=$("scoreBox"); box.innerHTML="";
      order.forEach(k=>{ const row=document.createElement("div"); row.className="score-row"; row.innerHTML=`<span>${facultyInfo[k].emoji} ${facultyInfo[k].name}</span><strong>${scores[k]}</strong>`; box.appendChild(row); });
      show("result");
    }, 1300);
  }

  $("sendBtn").addEventListener("click",()=>{
    const payload=JSON.stringify({type:"sorting_result",faculty:selectedFaculty,scores});
    if(tg?.sendData){ tg.sendData(payload); setTimeout(()=>tg.close(),350); }
    else alert("Bu sahifa Telegram Web App ichida ochilishi kerak.");
  });
})();
