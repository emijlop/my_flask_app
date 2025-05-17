from flask import render_template, flash, redirect, url_for, request
from flaskapp import app, db
from flaskapp.models import BlogPost, IpView, Day
from flaskapp.forms import PostForm
import datetime
from flaskapp.models import UkData

import pandas as pd
import numpy as np
import json
import plotly
import plotly.express as px


# Route for the home page, which is where the blog posts will be shown
@app.route("/")
@app.route("/home")
def home():
    # Querying all blog posts from the database
    posts = BlogPost.query.all()
    return render_template('home.html', posts=posts)


# Route for the about page
@app.route("/about")
def about():
    return render_template('about.html', title='About page')


# Route to where users add posts (needs to accept get and post requests)
@app.route("/post/new", methods=['GET', 'POST'])
def new_post():
    form = PostForm()
    if form.validate_on_submit():
        post = BlogPost(title=form.title.data, content=form.content.data, user_id=1)
        db.session.add(post)
        db.session.commit()
        flash('Your post has been created!', 'success')
        return redirect(url_for('home'))
    return render_template('create_post.html', title='New Post', form=form)


@app.route('/dashboard')
def dashboard():
    try:
        # Original page views visualization
        days = Day.query.all()
        if days:
            df_views = pd.DataFrame([{'Date': day.id, 'Page views': day.views} for day in days])
            fig_views = px.bar(df_views, x='Date', y='Page views', title='Daily Page Views')
            views_graphJSON = json.dumps(fig_views, cls=plotly.utils.PlotlyJSONEncoder)
        else:
            # Create empty chart if no data
            fig_views = px.bar(x=['No Data'], y=[0], title='No Page View Data Available')
            views_graphJSON = json.dumps(fig_views, cls=plotly.utils.PlotlyJSONEncoder)
        
        # Gender equality visualization
        uk_data = UkData.query.all()
        
        # Convert to DataFrame for easier manipulation
        df_gender = pd.DataFrame([{
            'constituency_name': data.constituency_name,
            'region': data.region,
            'female_percentage': data.c11Female,
            'lab_vote_pct': (data.LabVote19 / data.TotalVote19 * 100) if (data.TotalVote19 and data.LabVote19 is not None) else 0,
            'total_votes': data.TotalVote19 if data.TotalVote19 else 1  # Prevent zero values
        } for data in uk_data])
        
        # Fill NaN values with 0
        df_gender = df_gender.fillna(0)
        
        # Create the gender visualization
        fig_gender = px.scatter(df_gender,
                            x='female_percentage',
                            y='lab_vote_pct',
                            color='region',
                            size='total_votes',
                            hover_name='constituency_name',
                            labels={
                                'female_percentage': 'Female Population (%)',
                                'lab_vote_pct': 'Labour Vote Share (%)',
                                'region': 'UK Region'
                            },
                            title='Female Population vs. Labour Party Support')
        
        # Configure layout
        fig_gender.update_layout(
            xaxis_title='Female Population Percentage',
            yaxis_title='Labour Vote Share (%)',
            legend_title='UK Region',
            height=600
        )
        
        gender_graphJSON = json.dumps(fig_gender, cls=plotly.utils.PlotlyJSONEncoder)
        
        # Create the vulnerable groups visualization
        df_vulnerable = pd.DataFrame([{
            'constituency_name': data.constituency_name,
            'region': data.region,
            'female_pct': data.c11Female,
            'student_pct': data.c11FulltimeStudent,
            'retired_pct': data.c11Retired,
            'homeowner_pct': data.c11HouseOwned,  # This was missing in your original code
            'lab_vote_pct': (data.LabVote19 / data.TotalVote19 * 100) if (data.TotalVote19 and data.LabVote19 is not None) else 0,
            'con_vote_pct': (data.ConVote19 / data.TotalVote19 * 100) if (data.TotalVote19 and data.ConVote19 is not None) else 0,
            'ld_vote_pct': (data.LDVote19 / data.TotalVote19 * 100) if (data.TotalVote19 and data.LDVote19 is not None) else 0
        } for data in uk_data])
        
        # Fill NaN values with 0
        df_vulnerable = df_vulnerable.fillna(0)
        
        # Calculate vulnerable group indicators
        df_vulnerable['female_non_homeowner'] = df_vulnerable['female_pct'] * (100 - df_vulnerable['homeowner_pct']) / 100
        df_vulnerable['female_student'] = df_vulnerable['female_pct'] * df_vulnerable['student_pct'] / 100
        df_vulnerable['female_retired'] = df_vulnerable['female_pct'] * df_vulnerable['retired_pct'] / 100
        
        # Simplify the analysis - just use nationwide data rather than by region
        # This will be more reliable and avoid empty/sparse data issues
        
        # High female non-homeowner areas (top 25%)
        high_non_homeowner = df_vulnerable[df_vulnerable['female_non_homeowner'] > 
                                        df_vulnerable['female_non_homeowner'].quantile(0.75)]
        
        # High female student areas (top 25%)
        high_student = df_vulnerable[df_vulnerable['female_student'] > 
                                    df_vulnerable['female_student'].quantile(0.75)]
        
        # High female retired areas (top 25%)
        high_retired = df_vulnerable[df_vulnerable['female_retired'] > 
                                    df_vulnerable['female_retired'].quantile(0.75)]
        
        # Prepare data for plotting
        groups = ['Female Non-Homeowners', 'Female Students', 'Female Retired']
        
        # Labour
        lab_values = [
            high_non_homeowner['lab_vote_pct'].mean(),
            high_student['lab_vote_pct'].mean(),
            high_retired['lab_vote_pct'].mean()
        ]
        
        # Conservative
        con_values = [
            high_non_homeowner['con_vote_pct'].mean(),
            high_student['con_vote_pct'].mean(),
            high_retired['con_vote_pct'].mean()
        ]
        
        # Liberal Democrats
        ld_values = [
            high_non_homeowner['ld_vote_pct'].mean(),
            high_student['ld_vote_pct'].mean(),
            high_retired['ld_vote_pct'].mean()
        ]
        
        # Replace NaN with 0
        lab_values = [0 if np.isnan(x) else x for x in lab_values]
        con_values = [0 if np.isnan(x) else x for x in con_values]
        ld_values = [0 if np.isnan(x) else x for x in ld_values]
        
        # Create plot data
        plot_data = []
        for i, group in enumerate(groups):
            plot_data.append({'Group': group, 'Party': 'Labour', 'Support': lab_values[i]})
            plot_data.append({'Group': group, 'Party': 'Conservative', 'Support': con_values[i]})
            plot_data.append({'Group': group, 'Party': 'Liberal Democrats', 'Support': ld_values[i]})
        
        df_plot = pd.DataFrame(plot_data)
        
        # Create the vulnerable groups visualization
        fig_vulnerable = px.bar(df_plot, 
                            x='Group', 
                            y='Support', 
                            color='Party',
                            barmode='group',
                            labels={
                                'Support': 'Party Support (%)',
                                'Group': 'Vulnerable Female Groups',
                                'Party': 'Political Party'
                            },
                            title='Party Support Among Vulnerable Female Groups',
                            color_discrete_map={
                                'Labour': '#E4003B', 
                                'Conservative': '#0087DC', 
                                'Liberal Democrats': '#FAA61A'
                            })
        
        # Configure layout
        fig_vulnerable.update_layout(
            height=500,
            xaxis_title='Vulnerable Female Groups',
            yaxis_title='Average Party Support (%)',
            legend_title='Political Party'
        )
        
        vulnerable_graphJSON = json.dumps(fig_vulnerable, cls=plotly.utils.PlotlyJSONEncoder)
        
        return render_template('dashboard.html',
                            title='Dashboard',
                            views_graph=views_graphJSON,
                            gender_graph=gender_graphJSON,
                            vulnerable_graph=vulnerable_graphJSON)
                            
    except Exception as e:
        # Log the error for debugging
        print(f"Dashboard error: {str(e)}")
        flash(f"An error occurred: {str(e)}", "danger")
        return render_template('dashboard.html', title='Dashboard Error')

@app.before_request
def before_request_func():
    day_id = datetime.date.today()  # get our day_id
    client_ip = request.remote_addr  # get the ip address of where the client request came from

    query = Day.query.filter_by(id=day_id)  # try to get the row associated to the current day
    if query.count() > 0:
        # the current day is already in table, simply increment its views
        current_day = query.first()
        current_day.views += 1
    else:
        # the current day does not exist, it's the first view for the day.
        current_day = Day(id=day_id, views=1)
        db.session.add(current_day)  # insert a new day into the day table

    query = IpView.query.filter_by(ip=client_ip, date_id=day_id)
    if query.count() == 0:  # check if it's the first time a viewer from this ip address is viewing the website
        ip_view = IpView(ip=client_ip, date_id=day_id)
        db.session.add(ip_view)  # insert into the ip_view table

    db.session.commit()  # commit all the changes to the database
