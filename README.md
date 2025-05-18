<div align="center">
  <h4 align="center">rater: a web rating service for osu! beatmaps</h4>
  <p align="center">
    <code>git clone https://github.com/x2corp/rater.git</code><br>
    <code>cd rater && cp ext/.env.example .env && nano .env</code><br>
    <code>mysql -u user -p rater < db/schema.sql</code><br>
    <code>pip install -r ext/requirements.txt</code><br>
    <code>python app.py</code><br>
  </p>
  Install MySQL >= 9.1 and <code>CREATE DATABASE rater;</code> before running this.<br>
  Thank you to Apollo for providing old OMDB data; this is available at <code>ext/omdb.sql</code> for testing.
</div>