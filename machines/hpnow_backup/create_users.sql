##create user 'cinf_reader'@'%' identified by 'cinf_reader';
##grant select on cinfdata.* to 'cinf_reader'@'%';
##grant all on cinfdata.plot_com to 'cinf_reader'@'%';
##grant all on cinfdata.plot_com_in to 'cinf_reader'@'%';
##grant all on cinfdata.plot_com_out to 'cinf_reader'@'%';
##grant all on cinfdata.short_links to 'cinf_reader'@'%';

## Exampe for the user that will log the lab environment
##create user 'hpnow'@'%' identified by 'hpnow';
##grant all on cinfdata.dateplots_hpnow to 'hpnow'@'%';
##grant all on cinfdata.dateplots_descriptions to 'hpnow'@'%';
##grant all on cinfdata.xy_values_hpnow to 'hpnow'@'%';
##grant all on cinfdata.measurements_hpnow to 'hpnow'@'%';

## Example for a user called proactive
#create user 'proactive'@'%' identified by proactive'';
#grant all on cinfdata.xy_values_proactive to 'proactive'@'%';
#grant all on cinfdata.measurements_proactive to 'proactive'@'%';
#grant all on cinfdata.dateplots_proactive to 'proactive'@'%';
#grant all on cinfdata.dateplots_descriptions to 'proactive'@'%';
#grant all on cinfdata.measurements_dummy to 'proactive'@'%';
#grant all on cinfdata.xy_values_dummy to 'proactive'@'%';
