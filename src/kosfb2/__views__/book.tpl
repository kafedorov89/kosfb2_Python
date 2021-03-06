{% extends "base.html" %}

{% block head%}
	<link rel="stylesheet" type="text/css" href="/css/style.css" />
	<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
{% endblock %}

{% block title %}
	Библиотека книг в формате fb2. Читай то, что хочешь бесплатно и в любое время.
{% endblock %}

{% block uploadbook %}
	<form action="/uploadbook" method="post" enctype="multipart/form-data">		
		<!-- Кнопка открытия диалога загрузки книг -->
		<div class="controls">	
	  		<input type="file" multiple="multiple" name="uploadfiles"><br>
	  		<input type="submit" name="startupload" value="Загрузить книги">
		</div>
	</form>
	
	{% if uploading == 'True' %}					
	<a href="/viewuploadlog">
		<br> Просмотреть отчет о загрузке книг <br>
	</a>
	{% endif %}
{% endblock %}

{% block message %}
	<div class="controls">
		{{message}}
	</div>
{% endblock %}

{% block findbook %}
	<form action="/findbook" accept-charset="UTF-8" method="post" id="findbookform">	
		<div class="controls">
			<label> Слово для поиска: </label>
			<input type="text" maxlength="400" name="findkeyword" size="50" value="{{findkeyword}}" title="Введите ключевые слова для поиска." class="formtext" /><br>
			Искать в:<br>
			<input type="radio" name="findtype" value="0" {{find_chkd[0]}}> названии <br>
			<input type="radio" name="findtype" value="1" {{find_chkd[1]}}> имени автора <br>
			<input type="radio" name="findtype" value="2" {{find_chkd[2]}}> названии серии <br>
			<input type="radio" name="findtype" value="3" {{find_chkd[3]}}> названии издательской серии <br>
		</div>
		
		<div class="controls">
			Сортировать по:<br>
			<input type="radio" name="grouptype" value="0" {{group_chkd[0]}}> жанрам <br>
			<input type="radio" name="grouptype" value="1" {{group_chkd[1]}}> сериям <br>
			<input type="radio" name="grouptype" value="2" {{group_chkd[2]}}> издательским сериям <br>
			<input type="radio" name="grouptype" value="3" {{group_chkd[3]}}> авторам <br>
		</div>
	
		<!-- Кнопка запуска поиска книг -->	
		<div class="controls">
			<input type="submit" id="findsubmit" value="Найти" class="formsubmit" />
		</div>
	</form>
{% endblock %}

{% block pgctrl %}
	<div class="row">
	<form action="/showbook" method="post" id="pgnavform">
	    <input type="hidden" name="pgnavstep" value="0">
	    <div class="pgnavbutton">
	    	<a href="javascript:;" onclick="oFormObject = document.forms['pgnavform']; oFormObject.elements['pgnavstep'].value = '-1'; oFormObject.submit();">
	    		<- Предыдущая<br> страница
	    	</a> 
	    </div>
	    <div id="pgnavtext">
	    	Текущая страница: <input type="text" size="4" name="pagenumb" value={{pagenumb + 1}} readonly><br>
	    	Кол-во книг на странице: <input type="text" size="4" name="pagebookcount" value={{pagebookcount}}>
	    </div>
	    <div class="pgnavbutton">
	    	<a href="javascript:;" onclick="oFormObject = document.forms['pgnavform']; oFormObject.elements['pgnavstep'].value = '1'; oFormObject.submit();">
	    		Следующая<br> страница ->
	    	</a>
	    </div>
	</form>
	</div>
{% endblock %}

{% block showbook %}
    {% if books|length > 0 %}
	    По вашему запросу найдено {{books|length}} книг
	    {% for book in books %}
	    <div class="book-description">
			<div class="row">
	
				<!-- Изображение обложки книги-->
				<div id="book-cover">
					<img src="{{book['CoverFile']}}" alt="Изображение обложки не найдено" title="" width="120" height="180" />
				</div>
				
				<!-- Текстовая информация о книге -->
				<div id="book-text-desc">
					<!-- Название -->
						Название:
						{% if book['Title'] is not none%}
							{{book['Title']}};<br>
						{% else %}
							--- <br>
						{% endif %}
					
					<!-- Авторы -->
						Авторы:
						{% if book['Authors'] is not none and book['Authors']|length > 0 %}
							{% for author in book['Authors'] %}
								{{author}};
							{% endfor %}<br>
						{% else %}
							--- <br>
						{% endif %}
					
					<!-- Жанры -->
						Жанры:
						{% if book['Genres'] is not none and book['Genres']|length > 0 %}
							{% for genre in book['Genres'] %}
								{{genre}};
							{% endfor %}<br>
						{% else %}
							--- <br>
						{% endif %}
					
					<!-- Серии -->
						Серии: 
						{% if book['Sequences'] is not none and book['Sequences']|length > 0 %}
							{% for sequence in book['Sequences'] %}
								{{sequence}};
							{% endfor %}<br>
						{% else %}
							--- <br>
						{% endif %}
						
					<!-- Издательские серии -->
						Издатель: {{book['Publisher']}}<br>
						
						Издательские серии: 
						{% if book['Sequences'] is not none and book['PubSequences']|length > 0 %}
							{% for sequence in book['PubSequences'] %}
								{{sequence}};
							{% endfor %}<br>
						{% else %}
							--- <br>
						{% endif %}
				</div>
				
				<!-- Кнопка для скачивания книги-->
				<div id="book-download">
					<a href="{{book['ZipFile']}}">Скачать</a>
				</div>
			</div>
		</div>
		<div class="separator"></div>
		{% endfor %}
	{% else %}
		<div class="empty-book-list">По данным условиям поиска книги не найдены</div>
	{% endif %}
{% endblock %} 
