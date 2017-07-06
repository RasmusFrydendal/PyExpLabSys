#BACKUP_DIR='/home/hpnow/backup/'
BACKUP_DIR="$@"

for table in $(mysql --defaults-extra-file=/home/hpnow/PyExpLabSys/machines/hpnow_backup/sql_config.cnf -B -s cinfdata -e 'show tables')
do
    mysqldump --defaults-extra-file=/home/hpnow/PyExpLabSys/machines/hpnow_backup/sql_config.cnf --lock-tables=false cinfdata $table | gzip >"$BACKUP_DIR/$table.sql.gz"
done
