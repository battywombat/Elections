Project URL: Sample-env.izd8ig29bv.us-west-2.elasticbeanstalk.com 

Most of the relevant data on what the website does should be in the presentation,
but theres a few things I'd like to note.

Most important thing to note is that there are some holes in the data set.
Several districts were newly created or resized around the time of the 2010 census,
that can create weird anomalies in those districts.

I'd also like to note that if votes are left blank, then those questions will not be
considered.

If a district doesn't have any relevant votes attached to it, then it's assumed
that the vote will split evenly.

There aren't any browser restrictions. However, you might run into a problem
with screen size though: I capped the width of main seciton of the website
at 960px. Dealing with anything smaller would have required delving into my 
javascript knowledge, which I didn't want to do for this project.

I used the standard python sqlite3 package as the database backend mostly because
my application has very few concurrent writes, and shouldn't be under too heavy load.
If you ask the people who write sqlite, these are the performance tradeoffs you need
to consider.

Finally, I'd like to note I spent the last couple days before the due date bolting
on features once I realized what I'd built was way to simple. However, I
explictly kept myself from implementing several features I felt were out of scope
for what the project was supposed to be. For example, I considered being able
to search user results by name, but decided that withing the context of the
application, it made more sense if users were searchable based on comparing answers
rather than searching for a particular name.