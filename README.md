# The Cooler Regular Expressions Engine
Cooler (cool-RE, get it?) is a set of regular expression engines implemented from scratch in Python.

<html> 
	<img src="./images/cooler_banner_02.png.png" width="90%" align="center" alt="Cooler (cool-RE, get it?) is a set of regular expression engines implemented from scratch in Python, © Shaurya Agarwal" />  
</html>  

The goal is to implement 3 variants:
1. [A toy engine for learning](https://github.com/shauryashaurya/coolRE/tree/main/toy)
1. [One based on backtracking](https://github.com/shauryashaurya/coolRE/tree/main/backtracking)
1. [And lastly one based on Finite Automata](https://github.com/shauryashaurya/coolRE/tree/main/finite-automata)

## Why?
> Some people, when confronted with a problem, think "I know, I'll use regular expressions."
> 
> Now they have two problems.
>  
>  \- Jamie Zawinski / David Tilbrook (depending upon how far you read [this blog post](http://regex.info/blog/2006-09-15/247))

Regular expressions are interesting in their own right and a RE engine is not-too-hard-not-too-easy challenge.  

So why do this? For fun. 

Not to study how regex works, there's better ways to learn regex. 
But to learn, how to do more than just use regex.

Trying to build **the Cooler 3** - should be an interesting refresher in elementary Theory of Computation, Automata, Compilers.  


## What's in it for you?
As an engineer, I suspect you'd get the same value from coolRE as me.
Study the code or implement one of them on your own. 

I don't plan to make any of these implementations _comprehensive_ - meaning implementing every line and edge case of the specifications (listed in references below) but the main parts I build will conform to the specs. 

## References
What I'll use:
* https://www.youtube.com/watch?v=fgp0tKWYQWY
* https://www.regular-expressions.info/
* [The Crenshaw Tutorial](https://compilers.iecc.com/crenshaw/)
* https://github.com/python/cpython/blob/main/Lib/re.py
* https://xysun.github.io/posts/regex-parsing-thompsons-algorithm.html
* http://gsf.cococlyde.org/download
* https://ia801907.us.archive.org/8/items/glenn_fowler_interpretation_of_posix_standard/glenn_fowler_interpretation_of_posix_standard.pdf
* https://kean.blog/post/lets-build-regex and https://github.com/kean/Regex
* The POSIX ERE:
	* [Regular Expressions/POSIX-Extended Regular Expressions](https://en.wikibooks.org/wiki/Regular_Expressions/POSIX-Extended_Regular_Expressions)
	* At [Regular-Expressions.info](https://www.regular-expressions.info/posix.html)
* Other Regular Expressions specs (I don't know how much I'll use these, but, just in case...):
  * [PCRE](https://www.pcre.org/current/doc/html/pcre2pattern.html)
  * [ECMAScript 2022 aka JavaScript](https://tc39.es/ecma262/#sec-regexp-regular-expression-objects)
  * [From the GNU Manual](https://www.gnu.org/software/findutils/manual/html_node/find_html/Regular-Expressions.html)
	* [‘posix-basic’ regular expression syntax](https://www.gnu.org/software/findutils/manual/html_node/find_html/posix_002dbasic-regular-expression-syntax.html)
	* [‘posix-egrep’ regular expression syntax](https://www.gnu.org/software/findutils/manual/html_node/find_html/posix_002degrep-regular-expression-syntax.html)



---

Big thank you to all those who've done this before, I learned loads, your work helps a lot!


Cool! Here we go...
