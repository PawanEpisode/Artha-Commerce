/**
 * A signed-in student has their course on `/`, so the courses index is only the public catalog.
 * The check runs in the head, before the catalog paints, and ignores `/courses/ca` and the other syllabus pages.
 */
export const COURSES_INDEX_REDIRECT_SCRIPT = `(function(){try{var p=(location.pathname||'/').replace(/\\/$/,'')||'/';if(p!=='/courses')return;for(var i=0;i<localStorage.length;i++){var k=localStorage.key(i);if(/^sb-.+-auth-token$/.test(k)){var v=JSON.parse(localStorage.getItem(k)||'null');if(v&&v.access_token&&v.refresh_token){location.replace('/');return}}}}catch(e){}})()`
