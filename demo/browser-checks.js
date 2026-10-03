async (page) => {
  await page.evaluate(()=>document.fonts.ready);
  return await page.evaluate(()=>{
    const problems=[];
    const components=[...document.querySelectorAll('[data-component]')];
    for(const component of components){
      const bounds=component.getBoundingClientRect();
      const walker=document.createTreeWalker(component,NodeFilter.SHOW_TEXT);
      let text;
      while(text=walker.nextNode()){
        if(!text.textContent.trim())continue;
        const range=document.createRange();range.selectNodeContents(text);
        for(const r of range.getClientRects()){
          if(r.left<bounds.left-1||r.right>bounds.right+1||r.top<bounds.top-1||r.bottom>bounds.bottom+1)
            problems.push(component.dataset.component+': clipped '+text.textContent);
        }
      }
      if(component.dataset.component==='statsPanel'){
        const root=component.firstElementChild;
        const names=root.children[2].getBoundingClientRect();
        const rows=[...root.children[3].children];
        if(rows[0].getBoundingClientRect().top<names.bottom-1)problems.push('Stats rows overlap names');
        if(rows.at(-1).getBoundingClientRect().bottom>root.children[4].getBoundingClientRect().top+1)problems.push('Stats rows overlap footer');
        for(const row of rows){
          const columns=[...row.children].map(x=>x.getBoundingClientRect());
          if(columns[0].right>columns[1].left+1||columns[1].right>columns[2].left+1)problems.push('Stats columns overlap');
        }
      }
    }
    if(problems.length)throw new Error(problems.join('\n'));
    if(document.querySelectorAll('.capture').length!==7)throw new Error('Expected seven previews');
    return {previews:7,components:components.length,clippedText:0,overlappingRows:0};
  });
}
