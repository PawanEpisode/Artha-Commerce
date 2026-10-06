/**
 * A signed-in student has their course on `/`, so the courses index is only the public catalog.
 * The check runs in the head, before the catalog paints, and ignores `/courses/ca` and the other syllabus pages.
 * `?all=1` is the student's own "Explore other courses" choice, so it is never redirected.
 */
export const COURSES_INDEX_REDIRECT_SCRIPT = `(function(){try{var p=(location.pathname||'/').replace(/\\/$/,'')||'/';if(p!=='/courses'||/[?&]all=1(&|$)/.test(location.search||''))return;for(var i=0;i<localStorage.length;i++){var k=localStorage.key(i);if(/^sb-.+-auth-token$/.test(k)){var v=JSON.parse(localStorage.getItem(k)||'null');if(v&&v.access_token&&v.refresh_token){location.replace('/');return}}}}catch(e){}})()`
